import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { LocateFixed } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "../lib/i18n";
import type { GeoPoint } from "../lib/types";
import { Button } from "./ui";

// Pin — CSS bilan (Leaflet'ning standart rasm ikonkalari bundler bilan buziladi)
const PIN = L.divIcon({
  className: "",
  html: '<div class="workly-pin"></div>',
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

/**
 * Ish joyini xaritada belgilash: bosish yoki pinni surish. Check-in shu nuqtadan 200 m ichida
 * tekshiriladi (TZ 10), shuning uchun nuqta majburiy — tuman markazi taxmin sifatida olinmaydi.
 * Xarita: OpenStreetMap (kalitsiz); Yandex kaliti berilsa, plitkalar almashtiriladi.
 */
export function MapPicker({
  center,
  value,
  onChange,
}: {
  center: [number, number];
  value: GeoPoint | null;
  onChange: (p: GeoPoint) => void;
}) {
  const { t } = useI18n();
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.Marker | null>(null);
  const change = useRef(onChange);
  change.current = onChange;
  const [locating, setLocating] = useState(false);
  const [geoError, setGeoError] = useState(false);

  const place = (lat: number, lon: number) => {
    if (!map.current) return;
    if (!marker.current) {
      marker.current = L.marker([lat, lon], { icon: PIN, draggable: true }).addTo(map.current);
      marker.current.on("dragend", () => {
        const p = marker.current!.getLatLng();
        change.current({ lat: p.lat, lon: p.lng });
      });
    } else {
      marker.current.setLatLng([lat, lon]);
    }
  };

  useEffect(() => {
    if (!box.current || map.current) return;
    const m = L.map(box.current, { zoomControl: true, attributionControl: true }).setView(value ? [value.lat, value.lon] : center, value ? 17 : 14);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap",
    }).addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => {
      place(e.latlng.lat, e.latlng.lng);
      change.current({ lat: e.latlng.lat, lon: e.latlng.lng });
    });
    map.current = m;
    if (value) place(value.lat, value.lon);
    return () => {
      m.remove();
      map.current = null;
      marker.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tuman o'zgarsa — nuqta hali tanlanmagan bo'lsa, xarita o'sha tumanga suriladi
  useEffect(() => {
    if (map.current && !value) map.current.setView(center, 14);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center[0], center[1]]);

  const locate = () => {
    setLocating(true);
    setGeoError(false);
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        setLocating(false);
        const { latitude, longitude } = pos.coords;
        place(latitude, longitude);
        map.current?.setView([latitude, longitude], 17);
        change.current({ lat: latitude, lon: longitude });
      },
      () => {
        setLocating(false);
        setGeoError(true);
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  };

  return (
    <div className="space-y-2">
      <div ref={box} className="h-64 w-full overflow-hidden rounded-xl border border-mist" role="application" aria-label={t("order.mapHint")} />
      <p className={value ? "text-xs text-success" : "text-xs text-muted"}>{value ? t("order.pointSet") : t("order.mapHint")}</p>
      {geoError && <p className="text-xs text-danger">{t("order.geoDenied")}</p>}
      <Button variant="secondary" loading={locating} onClick={locate}>
        <LocateFixed size={18} aria-hidden /> {t("order.point")}
      </Button>
    </div>
  );
}
