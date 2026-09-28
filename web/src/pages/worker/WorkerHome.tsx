import { MapPin, MapPinned } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";

import { Countdown, JobCardView, useErrorText } from "../../components/shared";
import { Button, Card, Empty, ErrorBox, Page, Section, Spinner, Toggle } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useI18n } from "../../lib/i18n";
import { AssignmentCard } from "./WorkerJobs";
import { useAssignments, useJobActions, useOffers, useWorkerProfile } from "./hooks";

export default function WorkerHome() {
  const { t } = useI18n();
  const { me } = useAuth();
  const profile = useWorkerProfile();
  const verified = profile.data?.verification.status === "verified";
  const offers = useOffers(verified);
  const assignments = useAssignments(verified);
  const { accept, decline } = useJobActions();
  const errorText = useErrorText();
  const [available, setAvailable] = useState(false);
  const until = profile.data?.available_now_until;
  useEffect(() => setAvailable(Boolean(until && new Date(until).getTime() > Date.now())), [until]);
  const toggle = useMutation({
    mutationFn: (value: boolean) =>
      api<{ available_now: boolean }>("/worker/status", { body: { available_now: value } }),
    onSuccess: (r) => setAvailable(r.available_now),
  });

  const status = profile.data?.verification.status;
  const firstName = profile.data?.first_name ?? me?.full_name?.split(" ")[1] ?? "";

  return (
    <Page>
      <header className="flex items-center justify-between py-4">
        <img src="/brand/logo_320.webp" alt="Workly" className="h-8" />
        <span className="flex items-center gap-1 rounded-full bg-white px-3 py-1.5 text-sm shadow-[var(--shadow-card)]"><MapPin size={16} className="text-brand" aria-hidden /> {t("common.city")}</span>
      </header>
      <h1 className="text-2xl font-bold">{firstName ? t("home.hello", { name: firstName }) : t("home.helloAnon")}</h1>

      {profile.isLoading && <Spinner />}
      {status && status !== "verified" && (
        <Card className="mt-4 bg-brand-soft">
          <p className="font-medium">
            {status === "pending"
              ? t("home.verifyPending")
              : status === "rejected"
                ? t("home.verifyRejected")
                : t("home.verifyFirst")}
          </p>
          {status !== "pending" && (
            <Link to="/worker/profile" className="mt-3 block">
              <Button>{t("home.completeProfile")}</Button>
            </Link>
          )}
        </Card>
      )}

      {verified && (
        <>
          <Card className="mt-4">
            <Toggle
              checked={available}
              onChange={(v) => toggle.mutate(v)}
              label={t("home.availableNow")}
              hint={t("home.availableHint")}
            />
          </Card>

          <Link to="/jobs" className="relative mt-4 block overflow-hidden rounded-[var(--radius-card)] bg-brand p-5 text-white">
            <img src="/backgrounds/09_cobalt_waves_720.webp" alt="" className="absolute inset-0 h-full w-full object-cover opacity-60" />
            <span className="relative block text-xl font-bold">{t("home.nearby")}</span>
            <span className="relative block text-sm text-white/80">{t("home.nearbyHint")}</span>
            <MapPinned size={44} strokeWidth={1.6} className="absolute right-5 top-1/2 -translate-y-1/2 text-white/90" aria-hidden />
          </Link>

          <Section title={t("home.offers")}>
            <ErrorBox message={errorText(accept.error ?? decline.error)} />
            {offers.isLoading ? (
              <Spinner />
            ) : offers.data?.length ? (
              <div className="space-y-3">
                {offers.data.map((o) => (
                  <JobCardView
                    key={o.offer_id}
                    job={o}
                    extra={<Countdown until={o.expires_at} />}
                    footer={
                      <div className="grid grid-cols-2 gap-2">
                        <Button variant="secondary" onClick={() => decline.mutate(o.offer_id)} loading={decline.isPending && decline.variables === o.offer_id}>
                          {t("job.decline")}
                        </Button>
                        <Button onClick={() => accept.mutate(o.offer_id)} loading={accept.isPending && accept.variables === o.offer_id}>
                          {t("job.accept")}
                        </Button>
                      </div>
                    }
                  />
                ))}
              </div>
            ) : (
              <Empty text={t("home.noOffers")} />
            )}
          </Section>

          {!!assignments.data?.length && (
            <Section title={t("home.myJobs")}>
              <div className="space-y-3">
                {assignments.data.map((a) => (
                  <AssignmentCard key={a.assignment_id} a={a} />
                ))}
              </div>
            </Section>
          )}
        </>
      )}
    </Page>
  );
}
