import { describe, expect, it } from "vitest";
import { ApiError } from "../api";
import { LiveRequest, friendlyError, isAbort, statusOf, type LiveState } from "./liveRequest";

const abortErr = () => Object.assign(new Error("aborted"), { name: "AbortError" });

describe("error mapping", () => {
  it("maps statuses to messages", () => {
    expect(friendlyError(new ApiError(429, "rate limit exceeded"), "cube")).toContain("Too many cube requests");
    expect(friendlyError(new ApiError(504, "cube optimizer took longer than 45 s; try again"), "cube")).toBe("cube optimizer took longer than 45 s; try again.");
    expect(friendlyError(new ApiError(422, "Invalid inputs"), "cube")).toContain("invalid");
    expect(friendlyError(new ApiError(500, "computation failed for these inputs"), "cube")).toBe("computation failed for these inputs");
    expect(friendlyError(new Error(""), "cube")).toBe("Request failed.");
  });
  it("501 is 'unsupported', 422 lists the field messages, abort is detected", () => {
    expect(statusOf(new ApiError(501, "x"), "cube").unsupported).toBe(true);
    const s = statusOf(new ApiError(422, "Invalid inputs", [{ field: "gear[0].slot", message: "bad" }, { field: "", message: "general" }]), "cube");
    expect(s.fieldErrors).toEqual(["gear[0].slot: bad", "general"]);
    expect(s.unsupported).toBe(false);
    expect(isAbort(abortErr())).toBe(true);
    expect(isAbort(new Error("x"))).toBe(false);
  });
});

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
}
const tick = () => new Promise((r) => setTimeout(r, 0));

describe("LiveRequest", () => {
  it("loads once per key, keeps the answer while the next loads, and aborts the superseded request", async () => {
    const calls: { key: string; signal: AbortSignal; d: ReturnType<typeof deferred<string>> }[] = [];
    const states: LiveState<string>[] = [];
    const lr = new LiveRequest<string>((key, signal) => {
      const d = deferred<string>();
      calls.push({ key, signal, d });
      return d.promise;
    }, "test", (s) => states.push(s));
    lr.load("a");
    lr.load("a"); // same key while loading: aborts + re-asks (the hook only calls load on a settled key change)
    calls[1].d.resolve("A");
    await tick();
    expect(calls[0].signal.aborted).toBe(true);
    expect(lr.state.result).toBe("A");
    expect(lr.state.resultKey).toBe("a");
    lr.load("a"); // already answered: no request
    expect(calls).toHaveLength(2);
    lr.load("b");
    expect(lr.state.result).toBe("A"); // old answer stays while loading
    expect(lr.state.status.loading).toBe(true);
    lr.load("c"); // supersedes b
    calls[2].d.resolve("B");
    await tick();
    expect(lr.state.result).toBe("A"); // the aborted b answer is dropped
    calls[3].d.resolve("C");
    await tick();
    expect(lr.state.result).toBe("C");
    expect(lr.state.status.loading).toBe(false);
  });
  it("a 501 sticks for its group until reset; other failures do not", async () => {
    let n = 0;
    const lr = new LiveRequest<string>(async () => {
      n++;
      throw n === 1 ? new ApiError(501, "no") : new ApiError(500, "boom");
    }, "test");
    lr.load("k", "hero");
    await tick();
    expect(lr.state.status.unsupported).toBe(true);
    lr.load("k2", "hero");
    expect(n).toBe(1); // not asked again
    lr.load("k3", "fp_mage");
    await tick();
    expect(n).toBe(2);
    expect(lr.state.status.error).toBe("boom");
    lr.load("k3", "fp_mage"); // an error is retried on the same key
    await tick();
    expect(n).toBe(3);
    lr.reset();
    lr.load("k4", "hero");
    await tick();
    expect(n).toBe(4);
  });
  it("cancel stops loading without an error", async () => {
    const d = deferred<string>();
    const lr = new LiveRequest<string>((_k, signal) => {
      signal.addEventListener("abort", () => d.reject(abortErr()));
      return d.promise;
    }, "test");
    lr.load("a");
    lr.cancel();
    await tick();
    expect(lr.state.status).toMatchObject({ loading: false, error: null });
  });
});
