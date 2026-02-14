import { describe, expect, it } from "bun:test";
import { VERSION } from "../src/index.js";

describe("mcp-refcache", () => {
  describe("VERSION", () => {
    it("exports a version string", () => {
      expect(typeof VERSION).toBe("string");
    });

    it("matches semver format", () => {
      const semverPattern = /^\d+\.\d+\.\d+$/;
      expect(VERSION).toMatch(semverPattern);
    });

    it("matches package.json version", async () => {
      const packageJsonPath = new URL("../package.json", import.meta.url);
      const packageJson = await Bun.file(packageJsonPath).json();
      expect(VERSION).toBe(packageJson.version);
    });
  });
});
