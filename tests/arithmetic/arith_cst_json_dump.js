#!/usr/bin/env node

const Parser = require('tree-sitter');
const ARITH = require('.');

var args = process.argv.slice(2);

var fs = require("fs");
const sourceCode = fs.readFileSync(args[0]).toString();

const parser = new Parser();
parser.setLanguage(ARITH);
const tree = parser.parse(sourceCode);

console.log(JSON.stringify(tree.rootNode, ["type", "children"], 2))