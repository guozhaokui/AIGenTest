"""
模型加载器
负责加载 Qwen3-0.6B 模型并提供推理接口
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from typing import Optional
import config


class ModelLoader:
    """模型加载和管理"""

    def __init__(self):
        self.model: Optional[AutoModelForCausalLM] = None
        self.tokenizer: Optional[AutoTokenizer] = None
        self.device = config.DEVICE

    def load_model(self):
        """加载模型"""
        print(f"Loading model: {config.MODEL_NAME}")
        print(f"Precision: {config.PRECISION}")
        print(f"Device: {self.device}")

        # 根据精度设置量化配置
        if config.PRECISION == "int8":
            print("Using INT8 quantization...")
            self.model = AutoModelForCausalLM.from_pretrained(
                config.MODEL_NAME,
                load_in_8bit=True,
                device_map="auto",
                trust_remote_code=True,
                cache_dir=str(config.CACHE_DIR)
            )
        elif config.PRECISION == "int4":
            print("Using INT4 quantization...")
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                config.MODEL_NAME,
                quantization_config=quantization_config,
                device_map="auto",
                trust_remote_code=True,
                cache_dir=str(config.CACHE_DIR)
            )
        else:  # fp16
            print("Using FP16 precision...")
            self.model = AutoModelForCausalLM.from_pretrained(
                config.MODEL_NAME,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
                cache_dir=str(config.CACHE_DIR)
            )

        # 加载 tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            config.MODEL_NAME,
            trust_remote_code=True,
            cache_dir=str(config.CACHE_DIR)
        )

        print("✓ Model loaded successfully")

        # 打印显存占用
        if torch.cuda.is_available():
            memory_allocated = torch.cuda.memory_allocated() / 1024**3
            print(f"GPU Memory: {memory_allocated:.2f} GB")

    def generate(
        self,
        prompt: str,
        max_length: int = None,
        temperature: float = None,
        top_p: float = None
    ) -> str:
        """生成文本"""
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # 使用配置中的默认值
        max_length = max_length or config.MAX_LENGTH
        temperature = temperature if temperature is not None else config.TEMPERATURE
        top_p = top_p if top_p is not None else config.TOP_P

        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=max_length,
                temperature=temperature,
                top_p=top_p,
                do_sample=config.DO_SAMPLE,
                pad_token_id=self.tokenizer.eos_token_id
            )

        # Decode
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # 移除 prompt 部分，只返回生成的内容
        if generated_text.startswith(prompt):
            generated_text = generated_text[len(prompt):].strip()

        return generated_text

    def get_model_info(self) -> dict:
        """获取模型信息"""
        if self.model is None:
            return {"status": "not_loaded"}

        info = {
            "status": "loaded",
            "model_name": config.MODEL_NAME,
            "precision": config.PRECISION,
            "device": self.device,
        }

        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_memory_allocated"] = f"{torch.cuda.memory_allocated() / 1024**3:.2f} GB"
            info["gpu_memory_total"] = f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB"

        return info


# 全局模型实例
_model_loader: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    """获取全局模型加载器实例"""
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader
