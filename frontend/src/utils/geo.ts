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
  { name: "Gorzów Wielkopolski", aliases: ["gorzow", "gorzów"], lat: 52.7325, lng: 15.2369 },
];

export function matchPolishCity(query: string): PolishCityPreset | null {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return null;
  for (const city of POLISH_CITIES) {
    if (city.aliases.some((alias) => alias === normalized || alias.startsWith(normalized))) {
      return city;
    }
  }
  return null;
}

export async function geocodePolishLocation(
  query: string
): Promise<{ lat: number; lng: number; label: string } | null> {
  const cityHit = matchPolishCity(query);
  if (cityHit) {
    return { lat: cityHit.lat, lng: cityHit.lng, label: cityHit.name };
  }

  const trimmed = query.trim();
  if (!trimmed) return null;

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
    return { lat, lng, label: data[0].display_name };
  } catch {
    return null;
  }
}
