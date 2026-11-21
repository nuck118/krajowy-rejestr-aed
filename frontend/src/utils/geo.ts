import { apiUrl } from "../api/client";

export function haversineMeters(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number
): number {
  const R = 6_371_000;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const dPhi = toRad(lat2 - lat1);
  const dLambda = toRad(lng2 - lng1);
  const a =
    Math.sin(dPhi / 2) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function walkingMinutes(distanceMeters: number): number {
  return Math.max(1, Math.ceil(distanceMeters / 80));
}

export function formatDistance(distanceMeters: number): string {
  if (distanceMeters < 1000) {
    return `${Math.round(distanceMeters)} m`;
  }
  return `${(distanceMeters / 1000).toFixed(2)} km`;
}

export interface PolishCityPreset {
  name: string;
  aliases: string[];
  lat: number;
  lng: number;
}

export const POLISH_CITIES: PolishCityPreset[] = [
  { name: "Bydgoszcz", aliases: ["bydgoszcz"], lat: 53.1235, lng: 18.0084 },
  { name: "Warszawa", aliases: ["warszawa", "warsaw"], lat: 52.2297, lng: 21.0122 },
  { name: "Kraków", aliases: ["krakow", "kraków", "cracow"], lat: 50.0647, lng: 19.945 },
  { name: "Gdańsk", aliases: ["gdansk", "gdańsk"], lat: 54.352, lng: 18.6466 },
  { name: "Wrocław", aliases: ["wroclaw", "wrocław"], lat: 51.1079, lng: 17.0385 },
  { name: "Poznań", aliases: ["poznan", "poznań"], lat: 52.4064, lng: 16.9252 },
  { name: "Łódź", aliases: ["lodz", "łódź"], lat: 51.7592, lng: 19.456 },
  { name: "Szczecin", aliases: ["szczecin"], lat: 53.4285, lng: 14.5528 },
  { name: "Katowice", aliases: ["katowice"], lat: 50.2649, lng: 19.0238 },
  { name: "Lublin", aliases: ["lublin"], lat: 51.2465, lng: 22.5684 },
  { name: "Toruń", aliases: ["torun", "toruń"], lat: 53.0138, lng: 18.5984 },
  { name: "Białystok", aliases: ["bialystok", "białystok"], lat: 53.1325, lng: 23.1688 },
  { name: "Gdynia", aliases: ["gdynia"], lat: 54.5189, lng: 18.5305 },
  { name: "Rzeszów", aliases: ["rzeszow", "rzeszów"], lat: 50.0412, lng: 21.9991 },
  { name: "Olsztyn", aliases: ["olsztyn"], lat: 53.7784, lng: 20.4801 },
  { name: "Kielce", aliases: ["kielce"], lat: 50.8661, lng: 20.6286 },
  { name: "Opole", aliases: ["opole"], lat: 50.6751, lng: 17.9213 },
  { name: "Zielona Góra", aliases: ["zielona gora", "zielona góra"], lat: 51.9356, lng: 15.5062 },
  { name: "Gorzów Wielkopolski", aliases: ["gorzow", "gorzów", "gorzow wielkopolski", "gorzów wielkopolski"], lat: 52.7325, lng: 15.2369 },
];

export function matchPolishCity(query: string): PolishCityPreset | null {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return null;
  for (const city of POLISH_CITIES) {
    if (city.aliases.some((alias) => alias === normalized)) {
      return city;
    }
  }
  return null;
}

export interface GeocodedLocation {
  lat: number;
  lng: number;
  label: string;
  street_address?: string | null;
  city?: string | null;
  postal_code?: string | null;
  place_name?: string | null;
  isStreetLevel?: boolean;
}

export async function geocodePolishLocation(
  query: string
): Promise<GeocodedLocation | null> {
  const trimmed = query.trim();
  if (!trimmed) return null;

  const cityHit = matchPolishCity(trimmed);
  if (cityHit) {
    return {
      lat: cityHit.lat,
      lng: cityHit.lng,
      label: cityHit.name,
      city: cityHit.name,
      isStreetLevel: false,
    };
  }

  try {
    const resp = await fetch(
      apiUrl(`/api/v1/aeds/geocode?q=${encodeURIComponent(trimmed)}`),
      { headers: { Accept: "application/json" } }
    );
    if (resp.ok) {
      const data = (await resp.json()) as {
        latitude: number;
        longitude: number;
        label: string;
        street_address?: string | null;
        city?: string | null;
        postal_code?: string | null;
        place_name?: string | null;
      };
      if (Number.isFinite(data.latitude) && Number.isFinite(data.longitude)) {
        return {
          lat: data.latitude,
          lng: data.longitude,
          label: data.label,
          street_address: data.street_address,
          city: data.city,
          postal_code: data.postal_code,
          place_name: data.place_name,
          isStreetLevel: Boolean(data.street_address || data.place_name),
        };
      }
    }
  } catch {
    // Fall back to direct Nominatim if backend geocode endpoint is unreachable
  }

  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&countrycodes=pl&limit=1&q=${encodeURIComponent(trimmed)}`;
    const resp = await fetch(url, {
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) return null;
    const data = (await resp.json()) as Array<{
      lat: string;
      lon: string;
      display_name: string;
    }>;
    if (!data.length) return null;
    const lat = Number(data[0].lat);
    const lng = Number(data[0].lon);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return null;
    const shortLabel = data[0].display_name
      .split(",")
      .slice(0, 3)
      .map((s) => s.trim())
      .join(", ");
    return { lat, lng, label: shortLabel || data[0].display_name, isStreetLevel: true };
  } catch {
    return null;
  }
}

export async function reverseGeocodeLocation(
  lat: number,
  lng: number
): Promise<GeocodedLocation | null> {
  try {
    const resp = await fetch(
      apiUrl(
        `/api/v1/aeds/reverse-geocode?lat=${encodeURIComponent(lat.toFixed(6))}&lng=${encodeURIComponent(lng.toFixed(6))}`
      ),
      { headers: { Accept: "application/json" } }
    );
    if (!resp.ok) return null;
    const data = (await resp.json()) as {
      latitude: number;
      longitude: number;
      label: string;
      street_address?: string | null;
      city?: string | null;
      postal_code?: string | null;
      place_name?: string | null;
    };
    return {
      lat: data.latitude,
      lng: data.longitude,
      label: data.label,
      street_address: data.street_address,
      city: data.city,
      postal_code: data.postal_code,
      place_name: data.place_name,
      isStreetLevel: Boolean(data.street_address || data.place_name),
    };
  } catch {
    return null;
  }
}

export interface BrowserGpsFix {
  lat: number;
  lng: number;
  accuracyMeters: number;
}

export function acquirePreciseBrowserLocation(
  onInterimFix?: (fix: BrowserGpsFix) => void
): Promise<BrowserGpsFix> {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new Error("Geolocation unavailable"));
      return;
    }

    let bestFix: BrowserGpsFix | null = null;
    let settled = false;
    let watchId: number | null = null;
    let settleTimer: number | undefined;
    let hardTimer: number | undefined;

    const cleanup = () => {
      if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
      }
      if (settleTimer !== undefined) window.clearTimeout(settleTimer);
      if (hardTimer !== undefined) window.clearTimeout(hardTimer);
    };

    const finishWithBest = () => {
      if (settled || !bestFix) return;
      settled = true;
      cleanup();
      resolve(bestFix);
    };

    const fallbackLowAccuracy = (lastErr: GeolocationPositionError) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          if (settled) return;
          settled = true;
          cleanup();
          resolve({
            lat: Number(pos.coords.latitude.toFixed(6)),
            lng: Number(pos.coords.longitude.toFixed(6)),
            accuracyMeters: Math.round(pos.coords.accuracy || 1000),
          });
        },
        () => {
          if (settled) return;
          settled = true;
          cleanup();
          reject(lastErr);
        },
        { enableHighAccuracy: false, maximumAge: 0, timeout: 8000 }
      );
    };

    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        if (settled) return;
        const acc = Math.round(pos.coords.accuracy || 500);
        const candidate: BrowserGpsFix = {
          lat: Number(pos.coords.latitude.toFixed(6)),
          lng: Number(pos.coords.longitude.toFixed(6)),
          accuracyMeters: acc,
        };

        if (!bestFix || candidate.accuracyMeters < bestFix.accuracyMeters) {
          bestFix = candidate;
          onInterimFix?.(candidate);
        }

        if (candidate.accuracyMeters <= 35) {
          finishWithBest();
          return;
        }

        if (settleTimer === undefined) {
          settleTimer = window.setTimeout(finishWithBest, 2800);
        }
      },
      (err) => {
        if (settled) return;
        if (bestFix) {
          finishWithBest();
          return;
        }
        cleanup();
        fallbackLowAccuracy(err);
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 9000 }
    );

    hardTimer = window.setTimeout(() => {
      if (!settled && bestFix) {
        finishWithBest();
      }
    }, 9500);
  });
}
