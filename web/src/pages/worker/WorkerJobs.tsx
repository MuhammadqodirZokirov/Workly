import { Map as MapIcon, Phone } from "lucide-react";
import { useState } from "react";

import { Countdown, JobCardView, useErrorText } from "../../components/shared";
import { WorkdayTag, WorkerDayActions } from "../../components/workday";
import { Button, Chip, Empty, ErrorBox, Page, Spinner, TopBar } from "../../components/ui";
import { phonePretty } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { WorkerAssignment } from "../../lib/types";
import { useAssignments, useJobActions, useOffers, useOpenJobs, useWorkerProfile } from "./hooks";

type Tab = "offers" | "open" | "mine";

/** Tayinlangan ish: aniq manzil va ish beruvchi telefoni ochiladi (TZ 4, OS-12) */
export function AssignmentCard({ a }: { a: WorkerAssignment }) {
  const { t } = useI18n();
  const mapUrl = `https://yandex.uz/maps/?pt=${a.point.lon},${a.point.lat}&z=17&l=map`;
  return (
    <JobCardView
      job={a}
      extra={<WorkdayTag status={a.status} />}
      footer={
        <div className="space-y-3">
          <div className="space-y-2 rounded-xl bg-snow p-3 text-sm">
            <p>
              <b>{t("job.address")}:</b> {a.address_text}
            </p>
            {a.landmark && (
              <p>
                <b>{t("job.landmark")}:</b> {a.landmark}
              </p>
            )}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <a href={mapUrl} target="_blank" rel="noreferrer">
                <Button variant="secondary"><MapIcon size={18} aria-hidden /> {t("job.map")}</Button>
              </a>
              {a.employer_phone && (
                <a href={`tel:${a.employer_phone}`}>
                  <Button aria-label={phonePretty(a.employer_phone)}><Phone size={18} aria-hidden /> {t("job.call")}</Button>
                </a>
              )}
            </div>
          </div>
          <WorkerDayActions a={a} />
        </div>
      }
    />
  );
}

export default function WorkerJobs() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("offers");
  const verified = useWorkerProfile().data?.verification.status === "verified";
  const offers = useOffers(verified && tab === "offers");
  const open = useOpenJobs(verified && tab === "open");
  const mine = useAssignments(verified && tab === "mine");
  const { accept, take } = useJobActions();
  const errorText = useErrorText();
  const loading = offers.isLoading || open.isLoading || mine.isLoading;

  return (
    <>
      <TopBar title={t("nav.jobs")} />
      <Page>
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-2">
          <Chip active={tab === "offers"} onClick={() => setTab("offers")}>
            {t("home.offers")}
          </Chip>
          <Chip active={tab === "open"} onClick={() => setTab("open")}>
            {t("home.openJobs")}
          </Chip>
          <Chip active={tab === "mine"} onClick={() => setTab("mine")}>
            {t("home.myJobs")}
          </Chip>
        </div>
        <div className="mt-3 space-y-3">
          <ErrorBox message={errorText(accept.error ?? take.error)} />
          {!verified && <Empty text={t("home.verifyFirst")} />}
          {verified && loading && <Spinner />}
          {verified && tab === "offers" && offers.data && (offers.data.length ? offers.data.map((o) => (
            <JobCardView
              key={o.offer_id}
              job={o}
              extra={<Countdown until={o.expires_at} />}
              footer={<Button onClick={() => accept.mutate(o.offer_id)} loading={accept.isPending}>{t("job.accept")}</Button>}
            />
          )) : <Empty text={t("home.noOffers")} />)}
          {verified && tab === "open" && open.data && (open.data.length ? open.data.map((j) => (
            <JobCardView
              key={j.order_id}
              job={j}
              extra={<span className="text-xs text-muted">{t("job.slots", { n: j.open_slots })}</span>}
              footer={<Button onClick={() => take.mutate(j.order_id)} loading={take.isPending && take.variables === j.order_id}>{t("job.take")}</Button>}
            />
          )) : <Empty text={t("home.noJobs")} />)}
          {verified && tab === "mine" && mine.data && (mine.data.length ? mine.data.map((a) => <AssignmentCard key={a.assignment_id} a={a} />) : <Empty text={t("home.noJobs")} />)}
        </div>
      </Page>
    </>
  );
}
