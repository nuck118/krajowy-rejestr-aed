import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import { CrosshairIcon } from "../icons/Icons";

interface CoordinatePickerMapProps {
  locale: Locale;
  latitude: number;
  longitude: number;
  onChange: (lat: number, lng: number) => void;
  onUseMyLocation: () => void;
  isLocating: boolean;
}

const POSITRON_STYLE_URL =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

const FALLBACK_RASTER_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "carto-light": {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
    },
  },
  layers: [
    {
      id: "carto-light-layer",
      type: "raster",
      source: "carto-light",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

function pointGeoJson(lat: number, lng: number) {
  return {
    type: "FeatureCollection" as const,
    features: [
      {
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [lng, lat],
        },
        properties: {},
      },
    ],
  };
}

export function CoordinatePickerMap({
  locale,
  latitude,
  longitude,
  onChange,
  onUseMyLocation,
  isLocating,
}: CoordinatePickerMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const fallbackRef = useRef(false);
  const coordsRef = useRef({ latitude, longitude });
  const onChangeRef = useRef(onChange);

  const t = TRANSLATIONS[locale].submit;

  coordsRef.current = { latitude, longitude };
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: POSITRON_STYLE_URL,
      center: [coordsRef.current.longitude, coordsRef.current.latitude],
      zoom: 14.5,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const addPinLayer = () => {
      if (!map.getSource("picked-pin")) {
        map.addSource("picked-pin", {
          type: "geojson",
          data: pointGeoJson(coordsRef.current.latitude, coordsRef.current.longitude),
        });
        map.addLayer({
          id: "picked-pin-halo",
          type: "circle",
          source: "picked-pin",
          paint: {
            "circle-radius": 15,
            "circle-color": "#DC2626",
            "circle-opacity": 0.18,
          },
        });
        map.addLayer({
          id: "picked-pin-dot",
          type: "circle",
          source: "picked-pin",
          paint: {
            "circle-radius": 7,
            "circle-color": "#DC2626",
            "circle-stroke-width": 2.5,
            "circle-stroke-color": "#FFFFFF",
          },
        });
      }
      readyRef.current = true;
    };

    map.on("style.load", addPinLayer);
    map.on("load", addPinLayer);
    map.on("error", () => {
      if (!readyRef.current && !fallbackRef.current) {
        fallbackRef.current = true;
        map.setStyle(FALLBACK_RASTER_STYLE);
      }
    });

    map.on("click", (e) => {
      const nextLat = Number(e.lngLat.lat.toFixed(6));
      const nextLng = Number(e.lngLat.lng.toFixed(6));
      onChangeRef.current(nextLat, nextLng);
    });

    map.getCanvas().style.cursor = "crosshair";

    return () => {
      readyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    if (Number.isNaN(latitude) || Number.isNaN(longitude)) return;
    const src = map.getSource("picked-pin") as maplibregl.GeoJSONSource | undefined;
    if (src) {
      src.setData(pointGeoJson(latitude, longitude));
    }
    map.easeTo({ center: [longitude, latitude], duration: 350 });
  }, [latitude, longitude]);

  return (
    <div className="border border-[var(--border-hairline)] rounded-[3px] bg-[var(--bg-canvas)] flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--border-hairline)] bg-[var(--bg-surface)] flex items-center justify-between gap-2">
        <div>
          <span className="text-sm font-bold text-[var(--ink-primary)] block">
            {t.pickerTitle}
          </span>
          <span className="text-xs text-[var(--ink-secondary)]">{t.pickerSubtitle}</span>
        </div>
        <button
          type="button"
          onClick={onUseMyLocation}
          disabled={isLocating}
          className="h-8 px-3 rounded-[3px] border border-[var(--border-input)] hover:border-[var(--gov-blue)] bg-[var(--bg-canvas)] text-xs font-semibold text-[var(--gov-blue)] inline-flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shrink-0"
        >
          <CrosshairIcon className="w-3.5 h-3.5" />
          <span>{isLocating ? "..." : t.myGps}</span>
        </button>
      </div>
      <div ref={containerRef} className="w-full h-[310px] bg-[var(--bg-surface)]" />
      <div className="px-4 py-2 border-t border-[var(--border-hairline)] bg-[var(--bg-surface)] flex items-center justify-between font-mono text-xs text-[var(--ink-secondary)]">
        <span>Lat: {Number.isNaN(latitude) ? "-" : latitude.toFixed(6)}</span>
        <span>Lng: {Number.isNaN(longitude) ? "-" : longitude.toFixed(6)}</span>
      </div>
    </div>
  );
}
