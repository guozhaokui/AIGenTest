'use strict';

/**
 * @typedef {Object} Dimension
 * @property {string} id
 * @property {string} name
 * @property {string} description
 * @property {string[]} bonusCriteria
 * @property {string[]} penaltyCriteria
 */

/**
 * @typedef {Object} Question
 * @property {string} id
 * @property {string} prompt
 * @property {string[]} dimensionIds
 * @property {string} scoringRule
 * @property {string[]} exampleIds
 */

/**
 * @typedef {Object} Example
 * @property {string} id
 * @property {string} questionId
 * @property {string} imagePath
 * @property {string} note
 */

/**
 * @typedef {Object} Evaluation
 * @property {string} id
 * @property {string} questionId
 * @property {string} generatedImagePath
 * @property {Record<string, number>} scoresByDimension
 * @property {string} comment
 * @property {string} createdAt
 */

module.exports = {};


