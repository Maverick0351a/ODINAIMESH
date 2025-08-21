import { makeEchoTool } from "../dist/index.js";

const baseUrl = "http://127.0.0.1:8080";
const echo = makeEchoTool({ baseUrl, requireProof: false });
const out = await echo.invoke("hello langchain-odin-tools");
console.log("echo:", out);
