const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

class DatabaseService {
  constructor() {
    this.dbPath = path.resolve(__dirname, '../../data/aigc.db');
    this.db = null;
    this.initialized = false;
  }

  async init() {
    if (this.initialized) return;

    try {
      // 确保 data 目录存在
      const dataDir = path.dirname(this.dbPath);
      if (!fs.existsSync(dataDir)) {
        fs.mkdirSync(dataDir, { recursive: true });
      }

      // 打开数据库连接
      this.db = new Database(this.dbPath);
      console.log('Database connected:', this.dbPath);

      // 创建表
      this.createTables();

      // 准备常用的语句
      this.prepareStatements();

      this.initialized = true;
      console.log('Database initialized successfully');
    } catch (error) {
      console.error('Failed to initialize database:', error);
      throw error;
    }
  }

  createTables() {
    // 创建 AI 生成历史表 (替代 live-gen.json)
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS generations (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        model_id TEXT,
        driver_id TEXT,
        prompt TEXT NOT NULL,
        params TEXT,
        result TEXT,
        status TEXT DEFAULT 'completed',
        created_at TEXT NOT NULL,
        completed_at TEXT,
        metadata TEXT
      )
    `);

    // 创建索引
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_gen_type ON generations(type);
      CREATE INDEX IF NOT EXISTS idx_gen_driver ON generations(driver_id);
      CREATE INDEX IF NOT EXISTS idx_gen_created ON generations(created_at);
      CREATE INDEX IF NOT EXISTS idx_gen_status ON generations(status);
    `);


    // 创建统计表（可选，用于快速查询）
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS statistics (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);

    console.log('Database tables created');
  }

  prepareStatements() {
    // 准备常用的SQL语句
    this.statements = {
      // 插入生成记录
      insertGeneration: this.db.prepare(`
        INSERT INTO generations (
          id, type, model_id, driver_id, prompt, params,
          result, status, created_at, completed_at, metadata
        ) VALUES (
          @id, @type, @model_id, @driver_id, @prompt, @params,
          @result, @status, @created_at, @completed_at, @metadata
        )
      `),

      // 查询生成记录
      getGenerations: this.db.prepare(`
        SELECT * FROM generations
        ORDER BY created_at DESC
        LIMIT ?
      `),

      // 按条件查询生成记录
      getGenerationsByType: this.db.prepare(`
        SELECT * FROM generations
        WHERE type = ?
        ORDER BY created_at DESC
        LIMIT ?
      `),

      // 获取生成统计
      getGenerationStats: this.db.prepare(`
        SELECT
          COUNT(*) as total,
          COUNT(CASE WHEN type = 'image' THEN 1 END) as images,
          COUNT(CASE WHEN type = '3d' THEN 1 END) as models_3d,
          COUNT(CASE WHEN type = 'video' THEN 1 END) as videos,
          COUNT(CASE WHEN type = 'audio' THEN 1 END) as audios,
          COUNT(DISTINCT driver_id) as drivers_used,
          MIN(created_at) as first_generation,
          MAX(created_at) as last_generation
        FROM generations
      `),


      // 清理旧记录
      deleteOldGenerations: this.db.prepare(`
        DELETE FROM generations
        WHERE datetime(created_at) < datetime('now', '-' || ? || ' days')
      `),


      // Update generation record
      updateGeneration: this.db.prepare(`
        UPDATE generations
        SET result = @result, metadata = @metadata
        WHERE id = @id
      `),

      // Delete specific generation by ID
      deleteGeneration: this.db.prepare(`
        DELETE FROM generations
        WHERE id = ?
      `)
    };
  }

  // 保存生成记录
  async saveGeneration(data) {
    if (!this.initialized) await this.init();

    try {
      const record = {
        id: data.id,
        type: data.type,
        model_id: data.modelId || data.model_id || null,
        driver_id: data.driverId || data.driver_id || null,
        prompt: data.prompt,
        params: JSON.stringify(data.params || {}),
        result: JSON.stringify(data.result || {}),
        status: data.status || 'completed',
        created_at: data.createdAt || data.created_at || new Date().toISOString(),
        completed_at: data.completedAt || data.completed_at || new Date().toISOString(),
        metadata: JSON.stringify(data.metadata || {})
      };

      this.statements.insertGeneration.run(record);
      return true;
    } catch (error) {
      console.error('Failed to save generation:', error);
      throw error;
    }
  }

  // 批量保存生成记录（用于迁移）
  async saveGenerationsBatch(records) {
    if (!this.initialized) await this.init();

    const transaction = this.db.transaction((records) => {
      for (const record of records) {
        this.saveGeneration(record);
      }
    });

    try {
      transaction(records);
      console.log(`Saved ${records.length} generation records`);
      return true;
    } catch (error) {
      console.error('Failed to save batch:', error);
      throw error;
    }
  }

  // 更新生成记录
  async updateGeneration(id, updates) {
    if (!this.initialized) await this.init();

    try {
      const record = {
        id,
        result: JSON.stringify(updates.result || {}),
        metadata: JSON.stringify(updates.metadata || {})
      };

      const result = this.statements.updateGeneration.run(record);
      return result.changes > 0;
    } catch (error) {
      console.error('Failed to update generation:', error);
      throw error;
    }
  }

  // 删除特定生成记录
  async deleteGenerationById(id) {
    if (!this.initialized) await this.init();

    try {
      const result = this.statements.deleteGeneration.run(id);
      return result.changes > 0;
    } catch (error) {
      console.error('Failed to delete generation:', error);
      throw error;
    }
  }


  // 获取生成记录
  async getGenerations(limit = 100, filter = {}) {
    if (!this.initialized) await this.init();

    try {
      let records;

      if (filter.type) {
        records = this.statements.getGenerationsByType.all(filter.type, limit);
      } else {
        records = this.statements.getGenerations.all(limit);
      }

      // 解析 JSON 字段
      return records.map(record => ({
        ...record,
        params: JSON.parse(record.params || '{}'),
        result: JSON.parse(record.result || '{}'),
        metadata: JSON.parse(record.metadata || '{}')
      }));
    } catch (error) {
      console.error('Failed to get generations:', error);
      throw error;
    }
  }

  // 获取统计信息
  async getStats() {
    if (!this.initialized) await this.init();

    try {
      const stats = this.statements.getGenerationStats.get();
      return stats;
    } catch (error) {
      console.error('Failed to get stats:', error);
      throw error;
    }
  }


  // 清理旧数据
  async cleanup(daysToKeep = 30) {
    if (!this.initialized) await this.init();

    try {
      const genResult = this.statements.deleteOldGenerations.run(daysToKeep);

      console.log(`Cleaned up ${genResult.changes} old generations`);
      return {
        generations: genResult.changes
      };
    } catch (error) {
      console.error('Failed to cleanup:', error);
      throw error;
    }
  }

  // 关闭数据库连接
  close() {
    if (this.db) {
      this.db.close();
      this.db = null;
      this.initialized = false;
      console.log('Database connection closed');
    }
  }

  // 获取数据库信息
  getDatabaseInfo() {
    if (!this.initialized) return null;

    const info = {
      path: this.dbPath,
      size: fs.statSync(this.dbPath).size,
      tables: this.db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all(),
      generations: this.db.prepare("SELECT COUNT(*) as count FROM generations").get().count
    };

    return info;
  }
}

// 导出单例
module.exports = new DatabaseService();