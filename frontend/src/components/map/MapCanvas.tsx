import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import type { AEDRecord } from "../../types/aed";

interface MapCanvasProps {
  locale: Locale;
  aeds: AEDRecord[];
  selectedId: string | null;
  origin: { lat: number; lng: number };
  flyTarget: { lat: number; lng: number; zoom: number; seq: number } | null;
  onSelectAed: (id: string) => void;
  onBoundsChange: (bbox: string) => void;
}

const POSITRON_STYLE_URL =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

const FALLBACK_RASTER_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {
    "carto-light": {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
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

function toGeoJson(aeds: AEDRecord[], selectedId: string | null) {
  return {
    type: "FeatureCollection" as const,
    features: aeds.map((aed) => ({
      type: "Feature" as const,
      id: aed.id,
      geometry: {
        type: "Point" as const,
        coordinates: [aed.longitude, aed.latitude],
      },
      properties: {
        id: aed.id,
        status: aed.status,
        selected: aed.id === selectedId ? 1 : 0,
      },
    })),
  };
}

function originGeoJson(origin: { lat: number; lng: number }) {
  return {
    type: "FeatureCollection" as const,
    features: [
      {
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [origin.lng, origin.lat],
        },
        properties: {},
      },
    ],
  };
}

export function MapCanvas({
  locale,
  aeds,
  selectedId,
  origin,
  flyTarget,
  onSelectAed,
  onBoundsChange,
}: MapCanvasProps) {
  const t = TRANSLATIONS[locale].mapView;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const fallbackAppliedRef = useRef(false);

  const aedsRef = useRef(aeds);
  const selectedIdRef = useRef(selectedId);
  const originRef = useRef(origin);
  const onSelectRef = useRef(onSelectAed);
  const onBoundsRef = useRef(onBoundsChange);

  aedsRef.current = aeds;
  selectedIdRef.current = selectedId;
  originRef.current = origin;
  onSelectRef.current = onSelectAed;
  onBoundsRef.current = onBoundsChange;

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: POSITRON_STYLE_URL,
      center: [originRef.current.lng, originRef.current.lat],
      zoom: 13.5,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const addOverlaySourcesAndLayers = () => {
      if (!map.getSource("origin-point")) {
        map.addSource("origin-point", {
          type: "geojson",
          data: originGeoJson(originRef.current),
        });
        map.addLayer({
          id: "origin-halo",
          type: "circle",
          source: "origin-point",
          paint: {
            "circle-radius": 13,
            "circle-color": "#0F172A",
            "circle-opacity": 0.14,
          },
        });
        map.addLayer({
          id: "origin-dot",
          type: "circle",
          source: "origin-point",
          paint: {
            "circle-radius": 5.5,
            "circle-color": "#0F172A",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#FFFFFF",
          },
        });
      }

      if (!map.getSource("aeds")) {
        map.addSource("aeds", {
          type: "geojson",
          data: toGeoJson(aedsRef.current, selectedIdRef.current),
          cluster: true,
          clusterMaxZoom: 13,
          clusterRadius: 42,
        });

        map.addLayer({
          id: "aed-clusters",
          type: "circle",
          source: "aeds",
          filter: ["has", "point_count"],
          paint: {
            "circle-color": "#0F172A",
            "circle-radius": ["step", ["get", "point_count"], 15, 25, 19, 100, 23],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#FFFFFF",
          },
        });

        map.addLayer({
          id: "aed-cluster-count",
          type: "symbol",
          source: "aeds",
          filter: ["has", "point_count"],
          layout: {
            "text-field": ["get", "point_count_abbreviated"],
            "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
            "text-size": 11,
          },
          paint: {
            "text-color": "#FFFFFF",
          },
        });

        map.addLayer({
          id: "aed-points",
          type: "circle",
          source: "aeds",
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-color": [
              "case",
              ["==", ["get", "status"], "out_of_service"],
              "#475569",
              "#DC2626",
            ],
            "circle-radius": ["case", ["==", ["get", "selected"], 1], 10, 6.5],
            "circle-stroke-width": ["case", ["==", ["get", "selected"], 1], 3, 2],
            "circle-stroke-color": [
              "case",
              ["==", ["get", "selected"], 1],
              "#0F172A",
              "#FFFFFF",
            ],
          },
        });
      }

      readyRef.current = true;
    };

    map.on("style.load", () => {
      addOverlaySourcesAndLayers();
    });

    map.on("load", () => {
      addOverlaySourcesAndLayers();
      const b = map.getBounds();
      onBoundsRef.current(
        `${b.getWest().toFixed(5)},${b.getSouth().toFixed(5)},${b.getEast().toFixed(5)},${b.getNorth().toFixed(5)}`
      );
    });

    map.on("error", () => {
      if (!readyRef.current && !fallbackAppliedRef.current) {
        fallbackAppliedRef.current = true;
        map.setStyle(FALLBACK_RASTER_STYLE);
      }
    });

    map.on("click", "aed-clusters", async (e) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ["aed-clusters"] });
      const clusterId = features[0]?.properties?.cluster_id;
      const source = map.getSource("aeds") as maplibregl.GeoJSONSource | undefined;
      if (!source || clusterId === undefined) return;
      try {
        const zoom = await source.getClusterExpansionZoom(clusterId);
        const coords = (features[0].geometry as GeoJSON.Point).coordinates;
        map.easeTo({ center: [coords[0], coords[1]], zoom });
      } catch {
        // Ignore transient cluster zoom failures
      }
    });

    map.on("click", "aed-points", (e) => {
      const feature = e.features?.[0];
      const id = feature?.properties?.id;
      if (typeof id === "string") {
        onSelectRef.current(id);
      }
    });

    map.on("mouseenter", "aed-points", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "aed-points", () => {
      map.getCanvas().style.cursor = "";
    });
    map.on("mouseenter", "aed-clusters", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "aed-clusters", () => {
      map.getCanvas().style.cursor = "";
    });

    let moveTimer: number | undefined;
    map.on("moveend", () => {
      window.clearTimeout(moveTimer);
      moveTimer = window.setTimeout(() => {
        const b = map.getBounds();
        onBoundsRef.current(
          `${b.getWest().toFixed(5)},${b.getSouth().toFixed(5)},${b.getEast().toFixed(5)},${b.getNorth().toFixed(5)}`
        );
      }, 220);
    });

    return () => {
      window.clearTimeout(moveTimer);
      readyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const src = map.getSource("aeds") as maplibregl.GeoJSONSource | undefined;
    if (src) {
      src.setData(toGeoJson(aeds, selectedId));
    }
  }, [aeds, selectedId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const src = map.getSource("origin-point") as maplibregl.GeoJSONSource | undefined;
    if (src) {
      src.setData(originGeoJson(origin));
    }
  }, [origin]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyTarget) return;
    map.flyTo({
      center: [flyTarget.lng, flyTarget.lat],
      zoom: flyTarget.zoom,
      duration: 600,
    });
  }, [flyTarget]);

  return (
    <div className="relative w-full h-full bg-[var(--bg-surface)]">
      <div ref={containerRef} className="w-full h-full" />
      <div className="pointer-events-none absolute top-3 left-3 bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-[3px] px-2.5 py-1.5 flex items-center gap-3 text-[11px] font-mono text-[var(--ink-primary)]">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#DC2626] inline-block" />
          {t.legendOperational}
        </span>
        <span className="flex items-center gap-1.5 text-[var(--ink-secondary)]">
          <span className="w-2.5 h-2.5 rounded-full bg-[#475569] inline-block" />
          {t.legendOutOfService}
        </span>
      </div>
    </div>
  );
}
