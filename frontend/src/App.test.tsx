import ReactDOMServer from "react-dom/server";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders primary controls and initial guidance", () => {
    const html = ReactDOMServer.renderToString(<App />);
    expect(html).toContain("Mega AI");
    expect(html).toContain("Create session");
    expect(html).toContain("Start camera + streams");
    expect(html).toContain("Create a session, then start camera streaming.");
    expect(html).toContain("Processed stream will appear here.");
  });
});
