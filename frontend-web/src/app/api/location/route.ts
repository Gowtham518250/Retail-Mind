import { NextRequest, NextResponse } from 'next/server';

interface LocationResult {
  success: boolean;
  city: string;
  state?: string;
  pincode: string;
  area?: string;
  road?: string;
  formattedAddress: string;
  source: 'gps' | 'pincode' | 'fallback';
}

// Built-in Indian Postal Pincode Directory for top hubs and regional prefixes
const PINCODE_MAP: Record<string, { city: string; state: string; area: string }> = {
  // Bengaluru
  '560001': { city: 'Bengaluru', state: 'Karnataka', area: 'MG Road / Shivaji Nagar' },
  '560002': { city: 'Bengaluru', state: 'Karnataka', area: 'City Market / Chickpet' },
  '560004': { city: 'Bengaluru', state: 'Karnataka', area: 'Basavanagudi' },
  '560011': { city: 'Bengaluru', state: 'Karnataka', area: 'Jayanagar' },
  '560025': { city: 'Bengaluru', state: 'Karnataka', area: 'Richmond Town / Victoria Layout' },
  '560034': { city: 'Bengaluru', state: 'Karnataka', area: 'Koramangala' },
  '560037': { city: 'Bengaluru', state: 'Karnataka', area: 'Marathahalli' },
  '560038': { city: 'Bengaluru', state: 'Karnataka', area: 'Indiranagar' },
  '560066': { city: 'Bengaluru', state: 'Karnataka', area: 'Whitefield' },
  '560068': { city: 'Bengaluru', state: 'Karnataka', area: 'Madiwala / BTM Layout' },
  '560076': { city: 'Bengaluru', state: 'Karnataka', area: 'Bannerghatta Road / JP Nagar' },
  '560078': { city: 'Bengaluru', state: 'Karnataka', area: 'JP Nagar Phase 6' },
  '560085': { city: 'Bengaluru', state: 'Karnataka', area: 'Banashankari 3rd Stage' },
  '560095': { city: 'Bengaluru', state: 'Karnataka', area: 'Koramangala 4th Block' },
  '560100': { city: 'Bengaluru', state: 'Karnataka', area: 'Electronic City' },
  '560102': { city: 'Bengaluru', state: 'Karnataka', area: 'HSR Layout' },
  '560103': { city: 'Bengaluru', state: 'Karnataka', area: 'Bellandur / Outer Ring Road' },

  // Mumbai
  '400001': { city: 'Mumbai', state: 'Maharashtra', area: 'Fort / Colaba' },
  '400020': { city: 'Mumbai', state: 'Maharashtra', area: 'Churchgate / Marine Drive' },
  '400050': { city: 'Mumbai', state: 'Maharashtra', area: 'Bandra West' },
  '400051': { city: 'Mumbai', state: 'Maharashtra', area: 'Bandra Kurla Complex (BKC)' },
  '400053': { city: 'Mumbai', state: 'Maharashtra', area: 'Andheri West' },
  '400069': { city: 'Mumbai', state: 'Maharashtra', area: 'Andheri East' },
  '400076': { city: 'Mumbai', state: 'Maharashtra', area: 'Powai' },
  '400092': { city: 'Mumbai', state: 'Maharashtra', area: 'Borivali West' },

  // Delhi NCR
  '110001': { city: 'New Delhi', state: 'Delhi', area: 'Connaught Place' },
  '110016': { city: 'New Delhi', state: 'Delhi', area: 'Hauz Khas / Green Park' },
  '110019': { city: 'New Delhi', state: 'Delhi', area: 'Kalkaji / Nehru Place' },
  '110024': { city: 'New Delhi', state: 'Delhi', area: 'Lajpat Nagar / Defence Colony' },
  '110029': { city: 'New Delhi', state: 'Delhi', area: 'Safdarjung Enclave' },
  '110092': { city: 'Delhi', state: 'Delhi', area: 'Laxmi Nagar / Anand Vihar' },
  '122001': { city: 'Gurugram', state: 'Haryana', area: 'Old Gurugram' },
  '122002': { city: 'Gurugram', state: 'Haryana', area: 'DLF Phase 1 / Golf Course' },
  '201301': { city: 'Noida', state: 'Uttar Pradesh', area: 'Sector 1 to 15' },

  // Hyderabad
  '500001': { city: 'Hyderabad', state: 'Telangana', area: 'Abids / Koti' },
  '500032': { city: 'Hyderabad', state: 'Telangana', area: 'Gachibowli / Financial District' },
  '500034': { city: 'Hyderabad', state: 'Telangana', area: 'Banjara Hills' },
  '500081': { city: 'Hyderabad', state: 'Telangana', area: 'Madhapur / HITEC City' },
  '500084': { city: 'Hyderabad', state: 'Telangana', area: 'Kondapur' },

  // Chennai
  '600001': { city: 'Chennai', state: 'Tamil Nadu', area: 'George Town / Parrys' },
  '600004': { city: 'Chennai', state: 'Tamil Nadu', area: 'Mylapore' },
  '600017': { city: 'Chennai', state: 'Tamil Nadu', area: 'T Nagar' },
  '600020': { city: 'Chennai', state: 'Tamil Nadu', area: 'Adyar' },
  '600096': { city: 'Chennai', state: 'Tamil Nadu', area: 'Perungudi / OMR' },

  // Pune
  '411001': { city: 'Pune', state: 'Maharashtra', area: 'Pune Station / Camp' },
  '411004': { city: 'Pune', state: 'Maharashtra', area: 'Deccan / Shivaji Nagar' },
  '411014': { city: 'Pune', state: 'Maharashtra', area: 'Viman Nagar' },
  '411045': { city: 'Pune', state: 'Maharashtra', area: 'Baner / Balewadi' },
  '411057': { city: 'Pune', state: 'Maharashtra', area: 'Hinjawadi Infotech Park' },

  // Kolkata
  '700001': { city: 'Kolkata', state: 'West Bengal', area: 'BBD Bagh / Dalhousie' },
  '700019': { city: 'Kolkata', state: 'West Bengal', area: 'Ballygunge' },
  '700091': { city: 'Kolkata', state: 'West Bengal', area: 'Salt Lake Sector V' },
  '700156': { city: 'Kolkata', state: 'West Bengal', area: 'New Town' },

  // Ahmedabad
  '380001': { city: 'Ahmedabad', state: 'Gujarat', area: 'Lal Darwaja' },
  '380015': { city: 'Ahmedabad', state: 'Gujarat', area: 'Satellite / Vastrapur' },
  '380054': { city: 'Ahmedabad', state: 'Gujarat', area: 'Bodakdev / SG Highway' },
};

// Region prefix fallback for any 6-digit Indian Pincode
function getPrefixFallback(pincode: string): { city: string; state: string } {
  const p = pincode.slice(0, 2);
  switch (p) {
    case '11': return { city: 'New Delhi', state: 'Delhi' };
    case '12':
    case '13': return { city: 'Haryana', state: 'Haryana' };
    case '14':
    case '15':
    case '16': return { city: 'Punjab', state: 'Punjab' };
    case '17': return { city: 'Himachal Pradesh', state: 'Himachal Pradesh' };
    case '18':
    case '19': return { city: 'Jammu & Kashmir', state: 'Jammu and Kashmir' };
    case '20':
    case '21':
    case '22':
    case '23':
    case '24':
    case '25':
    case '26':
    case '27':
    case '28': return { city: 'Uttar Pradesh', state: 'Uttar Pradesh' };
    case '30':
    case '31':
    case '32':
    case '33':
    case '34': return { city: 'Jaipur', state: 'Rajasthan' };
    case '36':
    case '37':
    case '38':
    case '39': return { city: 'Ahmedabad', state: 'Gujarat' };
    case '40':
    case '41':
    case '42':
    case '43':
    case '44': return { city: 'Maharashtra', state: 'Maharashtra' };
    case '45':
    case '46':
    case '47':
    case '48': return { city: 'Madhya Pradesh', state: 'Madhya Pradesh' };
    case '49': return { city: 'Chhattisgarh', state: 'Chhattisgarh' };
    case '50': return { city: 'Hyderabad', state: 'Telangana' };
    case '51':
    case '52':
    case '53': return { city: 'Andhra Pradesh', state: 'Andhra Pradesh' };
    case '56':
    case '57':
    case '58':
    case '59': return { city: 'Bengaluru', state: 'Karnataka' };
    case '60':
    case '61':
    case '62':
    case '63':
    case '64': return { city: 'Chennai', state: 'Tamil Nadu' };
    case '67':
    case '68':
    case '69': return { city: 'Kerala', state: 'Kerala' };
    case '70':
    case '71':
    case '72':
    case '73':
    case '74': return { city: 'Kolkata', state: 'West Bengal' };
    case '75':
    case '76':
    case '77': return { city: 'Odisha', state: 'Odisha' };
    case '80':
    case '81':
    case '82':
    case '83':
    case '84':
    case '85': return { city: 'Patna', state: 'Bihar' };
    default: return { city: 'India', state: '' };
  }
}

// Bounding box heuristic for Indian cities
function getCityFromCoordinates(lat: number, lon: number): { city: string; state: string } {
  if (lat >= 12.83 && lat <= 13.15 && lon >= 77.45 && lon <= 77.78) {
    return { city: 'Bengaluru', state: 'Karnataka' };
  }
  if (lat >= 18.88 && lat <= 19.30 && lon >= 72.75 && lon <= 73.05) {
    return { city: 'Mumbai', state: 'Maharashtra' };
  }
  if (lat >= 28.40 && lat <= 28.88 && lon >= 76.85 && lon <= 77.35) {
    return { city: 'New Delhi', state: 'Delhi' };
  }
  if (lat >= 17.20 && lat <= 17.55 && lon >= 78.20 && lon <= 78.60) {
    return { city: 'Hyderabad', state: 'Telangana' };
  }
  if (lat >= 12.90 && lat <= 13.20 && lon >= 80.10 && lon <= 80.35) {
    return { city: 'Chennai', state: 'Tamil Nadu' };
  }
  if (lat >= 18.42 && lat <= 18.65 && lon >= 73.72 && lon <= 74.00) {
    return { city: 'Pune', state: 'Maharashtra' };
  }
  if (lat >= 22.45 && lat <= 22.65 && lon >= 88.25 && lon <= 88.48) {
    return { city: 'Kolkata', state: 'West Bengal' };
  }
  if (lat >= 22.95 && lat <= 23.15 && lon >= 72.45 && lon <= 72.70) {
    return { city: 'Ahmedabad', state: 'Gujarat' };
  }
  return { city: 'Local Area', state: 'India' };
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const latStr = searchParams.get('lat');
  const lonStr = searchParams.get('lon');
  const pincodeParam = searchParams.get('pincode')?.trim();

  // Mode 1: Pincode Lookup
  if (pincodeParam && /^\d{6}$/.test(pincodeParam)) {
    // 1. Check local high-speed cache
    const cached = PINCODE_MAP[pincodeParam];
    if (cached) {
      return NextResponse.json({
        success: true,
        city: cached.city,
        state: cached.state,
        area: cached.area,
        pincode: pincodeParam,
        formattedAddress: `${cached.area}, ${cached.city}, ${cached.state} - ${pincodeParam}`,
        source: 'pincode',
      } satisfies LocationResult);
    }

    // 2. Query official India Post API with 2.5s timeout
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2500);
      const res = await fetch(`https://api.postalpincode.in/pincode/${pincodeParam}`, {
        signal: controller.signal,
        headers: { Accept: 'application/json' },
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data[0]?.Status === 'Success' && Array.isArray(data[0]?.PostOffice) && data[0].PostOffice.length > 0) {
          const po = data[0].PostOffice[0];
          const area = po.Name || '';
          const city = po.District || po.Division || po.Block || '';
          const state = po.State || '';
          return NextResponse.json({
            success: true,
            city,
            state,
            area,
            pincode: pincodeParam,
            formattedAddress: [area, city, state, pincodeParam].filter(Boolean).join(', '),
            source: 'pincode',
          } satisfies LocationResult);
        }
      }
    } catch {
      // Fall through to prefix fallback
    }

    // 3. Fallback from prefix
    const prefix = getPrefixFallback(pincodeParam);
    return NextResponse.json({
      success: true,
      city: prefix.city,
      state: prefix.state,
      area: '',
      pincode: pincodeParam,
      formattedAddress: `${prefix.city}, ${prefix.state} - ${pincodeParam}`,
      source: 'fallback',
    } satisfies LocationResult);
  }

  // Mode 2: Reverse Geocode Coordinates
  if (latStr && lonStr) {
    const lat = parseFloat(latStr);
    const lon = parseFloat(lonStr);

    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      try {
        // Query OpenStreetMap Nominatim with server User-Agent and 3s timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);
        const res = await fetch(
          `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}&addressdetails=1`,
          {
            signal: controller.signal,
            headers: {
              'User-Agent': 'RetailMindCommercialWeb/1.0 (contact@retailmind.in)',
              Accept: 'application/json',
            },
          },
        );
        clearTimeout(timeoutId);

        if (res.ok) {
          const data = await res.json();
          const address = data?.address || {};

          // Clean city name (prevent "Bengaluru Urban" or "Bangalore South" weird names)
          let city = address.city || address.town || address.municipality || address.city_district || address.village || address.county || '';
          city = city.replace(/ Urban| Rural| South| North| East| West| District/gi, '').trim();

          const state = address.state || '';
          let pincode = String(address.postcode || '').replace(/\D/g, '').slice(0, 6);

          const road = address.road || address.street || address.highway || '';
          const area = address.neighbourhood || address.suburb || address.residential || address.subdistrict || address.commercial || '';
          const house = address.house_number || address.building || '';

          // If no city found from nominatim, use coordinate bounding box
          if (!city) {
            const fallback = getCityFromCoordinates(lat, lon);
            city = fallback.city;
          }

          // If pincode found in our map, refine area
          if (pincode && PINCODE_MAP[pincode]) {
            if (!city) city = PINCODE_MAP[pincode].city;
            if (!area) city = PINCODE_MAP[pincode].area;
          }

          const parts = [house, road, area, city, state].filter(Boolean);
          const formattedAddress = parts.join(', ') + (pincode ? ` - ${pincode}` : '');

          return NextResponse.json({
            success: true,
            city: city || 'Your City',
            state,
            pincode,
            area,
            road: [house, road].filter(Boolean).join(' '),
            formattedAddress: formattedAddress || 'Local Address',
            source: 'gps',
          } satisfies LocationResult);
        }
      } catch {
        // Fall back to bounding box
      }

      // High-accuracy fallback based on coordinates
      const box = getCityFromCoordinates(lat, lon);
      return NextResponse.json({
        success: true,
        city: box.city,
        state: box.state,
        pincode: '',
        area: '',
        road: '',
        formattedAddress: `${box.city}, ${box.state}`,
        source: 'gps',
      } satisfies LocationResult);
    }
  }

  return NextResponse.json(
    { success: false, message: 'Provide lat and lon or a 6-digit pincode.' },
    { status: 400 },
  );
}
