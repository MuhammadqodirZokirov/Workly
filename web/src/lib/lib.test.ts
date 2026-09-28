import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, tokens } from "./api";
import { dateTashkent, money, phonePretty } from "./format";
import { latinToCyrillic, translate } from "./i18n";

describe("translit (backend/workly/domain/translit.py bilan bir xil)", () => {
  it.each([
    ["Qurilish", "Қурилиш"],
    ["G'isht teruvchi", "Ғишт терувчи"],
    ["O'zbekiston", "Ўзбекистон"],
    ["Ta'mirdan keyin", "Таъмирдан кейин"],
    ["Elektrik", "Электрик"],
    ["Yangihayot", "Янгиҳаёт"],
    ["Mirzo Ulugʻbek", "Мирзо Улуғбек"],
    ["SHAHAR", "ШАҲАР"],
  ])("%s → %s", (latn, cyrl) => expect(latinToCyrillic(latn)).toBe(cyrl));

  it("brend nomi va joy egalari saqlanadi", () => {
    expect(latinToCyrillic("Workly ilovasi {n} kun")).toBe("Workly иловаси {n} кун");
  });

  it("translate uch tilda", () => {
    expect(translate("uz_latn", "job.slots", { n: 2 })).toBe("2 o'rin bo'sh");
    expect(translate("uz_cyrl", "job.slots", { n: 2 })).toBe("2 ўрин бўш");
    expect(translate("ru", "job.slots", { n: 2 })).toBe("Свободно мест: 2");
  });
});

describe("format", () => {
  it("pul — bo'sh joy bilan", () => expect(money(1450500)).toBe("1 450 500"));
  it("telefon", () => expect(phonePretty("+998901234567")).toBe("+998 90 123 45 67"));
  it("Toshkent sanasi", () => {
    // 2026-09-28 20:30 UTC = 29-sentabr 01:30 Toshkent
    expect(dateTashkent(0, Date.UTC(2026, 8, 28, 20, 30))).toBe("2026-09-29");
  });
});

describe("api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    tokens.clear();
  });

  const json = (status: number, body: unknown) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

  it("xato formati ApiError ga o'giriladi", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json(422, { code: "INVALID_PHONE", message: "x" }));
    await expect(api("/auth/otp/send", { body: {}, auth: false })).rejects.toMatchObject({
      status: 422,
      code: "INVALID_PHONE",
    } satisfies Partial<ApiError>);
  });

  it("parallel 401 — refresh faqat bir marta (rotatsiyada eski token qayta ishlatilmaydi)", async () => {
    tokens.save({ access_token: "old", refresh_token: "r1" });
    let refreshCalls = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        refreshCalls++;
        return json(200, { access_token: "new", refresh_token: "r2" });
      }
      const auth = (init?.headers as Record<string, string>)?.Authorization;
      return auth === "Bearer new" ? json(200, { ok: true }) : json(401, { code: "TOKEN_EXPIRED" });
    });
    const results = await Promise.all([api("/me"), api("/orders"), api("/worker/offers")]);
    expect(results).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(refreshCalls).toBe(1);
    expect(tokens.refresh).toBe("r2");
  });

  it("refresh rad etilsa — tokenlar tozalanadi", async () => {
    tokens.save({ access_token: "old", refresh_token: "bad" });
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input).endsWith("/auth/refresh") ? json(401, { code: "INVALID_REFRESH" }) : json(401, { code: "TOKEN_EXPIRED" }),
    );
    await expect(api("/me")).rejects.toBeInstanceOf(ApiError);
    expect(tokens.access).toBeNull();
  });
});
