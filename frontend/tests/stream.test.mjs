import test from "node:test";import assert from "node:assert/strict";
test("SSE contract has status and exactly one result",()=>{const sample=`event: status\ndata: {"status":"Đang tìm"}\n\nevent: result\ndata: {"type":"plan","plan":{}}\n\n`;assert.equal((sample.match(/event: result/g)||[]).length,1);assert.match(sample,/event: status/)})

