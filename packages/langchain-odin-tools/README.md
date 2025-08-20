# langchain-odin-tools (alpha)

LangChain tools wrapping ODIN Gateway endpoints.

## Install
```bash
npm install langchain-odin-tools odin-protocol-sdk@alpha
```

## Quick start (ESM)
```js
import { makeEchoTool, makeTranslateTool } from "langchain-odin-tools";

const baseUrl = "http://127.0.0.1:8080";
const echo = makeEchoTool({ baseUrl, requireProof: false });
const t = makeTranslateTool({ baseUrl, requireProof: false });

console.log(await echo.invoke("hello"));
console.log(await t.invoke({ text: "hi", to_sft: "beta@v1" }));
```

Notes:
- Uses odin-protocol-sdk@alpha.
- Set envs on the Gateway as needed for dynamic policy and keys.
