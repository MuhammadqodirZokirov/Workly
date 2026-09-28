import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useErrorText } from "../../components/shared";
import { Button, Card, Chip, ErrorBox, Field, Input, Page, Section, Select, Spinner, Tag, TopBar } from "../../components/ui";
import { api } from "../../lib/api";
import { useCatalog } from "../../lib/catalog";
import { pickName, useI18n } from "../../lib/i18n";
import type { Experience, WorkerProfile } from "../../lib/types";
import { useWorkerProfile } from "./hooks";

type Skill = { category_id: number; experience: Experience; specialization_ids: number[] };
type DocType = "id_card" | "passport";
const EXPERIENCES: Experience[] = ["none", "1_2", "3_5", "5_plus"];

export default function WorkerProfilePage() {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const catalog = useCatalog();
  const profile = useWorkerProfile();
  const errorText = useErrorText();
  const p = profile.data;
  const locked = p?.verification.status === "pending" || p?.verification.status === "verified";

  const [form, setForm] = useState({ last_name: "", first_name: "", middle_name: "", birth_date: "", gender: "" });
  const [districts, setDistricts] = useState<number[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [docType, setDocType] = useState<DocType>("id_card");
  const [docNumber, setDocNumber] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!p) return;
    setForm({
      last_name: p.last_name ?? "",
      first_name: p.first_name ?? "",
      middle_name: p.middle_name ?? "",
      birth_date: p.birth_date ?? "",
      gender: p.gender ?? "",
    });
    setDistricts(p.district_ids);
    setSkills(p.skills);
  }, [p]);

  const setProfile = (data: WorkerProfile) => qc.setQueryData(["worker", "profile"], data);

  const save = useMutation({
    mutationFn: () =>
      api<WorkerProfile>("/worker/profile", {
        method: "PUT",
        body: {
          ...(locked ? {} : {
            last_name: form.last_name,
            first_name: form.first_name,
            middle_name: form.middle_name,
            birth_date: form.birth_date || undefined,
            gender: form.gender || undefined,
          }),
          district_ids: districts,
          skills: skills.filter((s) => s.specialization_ids.length),
        },
      }),
    onSuccess: (data) => {
      setProfile(data);
      setSaved(true);
    },
  });

  const upload = useMutation({
    mutationFn: ({ kind, file }: { kind: string; file: File }) => {
      const form = new FormData();
      form.append("kind", kind);
      form.append("file", file);
      return api("/worker/files", { form });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["worker", "profile"] }),
  });

  const submit = useMutation({
    mutationFn: async () => {
      await save.mutateAsync();
      return api<WorkerProfile>("/worker/verification", { body: { doc_type: docType, doc_number: docNumber } });
    },
    onSuccess: setProfile,
  });

  if (profile.isLoading || catalog.loading) return <Spinner />;
  if (!p) return <ErrorBox message={errorText(profile.error)} />;

  const toggleDistrict = (id: number) =>
    setDistricts((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));
  const skillOf = (catId: number) => skills.find((s) => s.category_id === catId);
  const toggleSpec = (catId: number, specId: number) =>
    setSkills((all) => {
      const current = all.find((s) => s.category_id === catId) ?? { category_id: catId, experience: "none" as Experience, specialization_ids: [] };
      const ids = current.specialization_ids.includes(specId)
        ? current.specialization_ids.filter((x) => x !== specId)
        : [...current.specialization_ids, specId];
      return [...all.filter((s) => s.category_id !== catId), { ...current, specialization_ids: ids }];
    });
  const setExperience = (catId: number, experience: Experience) =>
    setSkills((all) => all.map((s) => (s.category_id === catId ? { ...s, experience } : s)));

  const files = new Set(p.files.map((f) => f.kind));
  const docKinds = docType === "id_card" ? ["id_card_front", "id_card_back"] : ["passport_main"];
  const fileLabel: Record<string, string> = {
    id_card_front: t("wp.idFront"),
    id_card_back: t("wp.idBack"),
    passport_main: t("wp.passportMain"),
    selfie: t("wp.selfie"),
  };
  const statusTone = { verified: "success", pending: "brand", rejected: "danger" } as const;

  return (
    <>
      <TopBar
        title={t("wp.title")}
        back
        right={
          <Tag tone={statusTone[p.verification.status as keyof typeof statusTone] ?? "muted"}>
            {t(`wp.status.${p.verification.status}`)}
          </Tag>
        }
      />
      <Page>
        {p.verification.status === "rejected" && (
          <ErrorBox message={p.verification.rejection_comment ?? p.verification.rejection_reason} />
        )}

        <Section title={t("profile.myProfile")}>
          <div className="space-y-3">
            {(["last_name", "first_name", "middle_name"] as const).map((k) => (
              <Field key={k} label={t(k === "last_name" ? "wp.lastName" : k === "first_name" ? "wp.firstName" : "wp.middleName")}>
                <Input value={form[k]} disabled={locked} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              </Field>
            ))}
            <Field label={t("wp.birthDate")}>
              <Input type="date" value={form.birth_date} disabled={locked} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} />
            </Field>
            <Field label={t("wp.gender")}>
              <div className="flex gap-2">
                {(["male", "female"] as const).map((g) => (
                  <Chip key={g} active={form.gender === g} onClick={() => !locked && setForm({ ...form, gender: g })}>
                    {t(g === "male" ? "wp.male" : "wp.female")}
                  </Chip>
                ))}
              </div>
            </Field>
          </div>
        </Section>

        <Section title={t("wp.districts")}>
          <div className="flex flex-wrap gap-2">
            {catalog.districts.map((d) => (
              <Chip key={d.id} active={districts.includes(d.id)} onClick={() => toggleDistrict(d.id)}>
                {pickName(d.name, lang)}
              </Chip>
            ))}
          </div>
        </Section>

        <Section title={t("wp.skills")}>
          <div className="space-y-3">
            {catalog.categories.map((c) => {
              const s = skillOf(c.id);
              return (
                <Card key={c.id}>
                  <p className="font-semibold">{pickName(c.name, lang)}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {c.specializations.map((sp) => (
                      <Chip key={sp.id} active={s?.specialization_ids.includes(sp.id)} onClick={() => toggleSpec(c.id, sp.id)}>
                        {pickName(sp.name, lang)}
                      </Chip>
                    ))}
                  </div>
                  {!!s?.specialization_ids.length && (
                    <div className="mt-3">
                      <Field label={t("wp.experience")}>
                        <Select value={s.experience} onChange={(e) => setExperience(c.id, e.target.value as Experience)}>
                          {EXPERIENCES.map((x) => (
                            <option key={x} value={x}>
                              {t(`exp.${x}`)}
                            </option>
                          ))}
                        </Select>
                      </Field>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        </Section>

        <div className="mt-4 space-y-2">
          <ErrorBox message={errorText(save.error)} />
          <Button variant="secondary" loading={save.isPending} onClick={() => save.mutate()}>
            {saved ? `✓ ${t("wp.saved")}` : t("common.save")}
          </Button>
        </div>

        {!locked && (
          <Section title={t("wp.docs")}>
            <div className="space-y-3">
              <div className="flex gap-2">
                <Chip active={docType === "id_card"} onClick={() => setDocType("id_card")}>
                  {t("wp.idCard")}
                </Chip>
                <Chip active={docType === "passport"} onClick={() => setDocType("passport")}>
                  {t("wp.passport")}
                </Chip>
              </div>
              <Field label={t("wp.docNumber")}>
                <Input value={docNumber} onChange={(e) => setDocNumber(e.target.value.toUpperCase())} maxLength={12} placeholder="AA1234567" />
              </Field>
              {[...docKinds, "selfie"].map((kind) => (
                <Card key={kind} className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">{fileLabel[kind]}</p>
                    {kind === "selfie" && <p className="text-xs text-muted">{t("wp.selfieHint")}</p>}
                  </div>
                  <label className="shrink-0 cursor-pointer">
                    {files.has(kind) ? <Tag tone="success">✓ {t("wp.uploaded")}</Tag> : <Tag tone="brand">📷 {t("wp.upload")}</Tag>}
                    {/* capture — telefonda to'g'ridan-to'g'ri kamera; selfie — old kamera (TZ 4: galereyadan emas) */}
                    <input
                      type="file"
                      accept="image/*"
                      capture={kind === "selfie" ? "user" : "environment"}
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) upload.mutate({ kind, file });
                        e.target.value = "";
                      }}
                    />
                  </label>
                </Card>
              ))}
              <ErrorBox message={errorText(upload.error ?? submit.error)} />
              <Button loading={submit.isPending || upload.isPending} disabled={!docNumber} onClick={() => submit.mutate()}>
                {t("wp.submit")}
              </Button>
            </div>
          </Section>
        )}
        {p.verification.status === "pending" && <p className="mt-6 text-center text-sm text-muted">{t("wp.submitted")}</p>}
      </Page>
    </>
  );
}
