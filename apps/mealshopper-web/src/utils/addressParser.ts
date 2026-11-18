import type { Address } from '../types/discovery';

const US_STATES: Record<string, string> = {
  alabama: 'AL',
  alaska: 'AK',
  arizona: 'AZ',
  arkansas: 'AR',
  california: 'CA',
  colorado: 'CO',
  connecticut: 'CT',
  delaware: 'DE',
  'district of columbia': 'DC',
  florida: 'FL',
  georgia: 'GA',
  hawaii: 'HI',
  idaho: 'ID',
  illinois: 'IL',
  indiana: 'IN',
  iowa: 'IA',
  kansas: 'KS',
  kentucky: 'KY',
  louisiana: 'LA',
  maine: 'ME',
  maryland: 'MD',
  massachusetts: 'MA',
  michigan: 'MI',
  minnesota: 'MN',
  mississippi: 'MS',
  missouri: 'MO',
  montana: 'MT',
  nebraska: 'NE',
  nevada: 'NV',
  'new hampshire': 'NH',
  'new jersey': 'NJ',
  'new mexico': 'NM',
  'new york': 'NY',
  'north carolina': 'NC',
  'north dakota': 'ND',
  ohio: 'OH',
  oklahoma: 'OK',
  oregon: 'OR',
  pennsylvania: 'PA',
  'rhode island': 'RI',
  'south carolina': 'SC',
  'south dakota': 'SD',
  tennessee: 'TN',
  texas: 'TX',
  utah: 'UT',
  vermont: 'VT',
  virginia: 'VA',
  washington: 'WA',
  'west virginia': 'WV',
  wisconsin: 'WI',
  wyoming: 'WY',
  'puerto rico': 'PR',
  guam: 'GU',
  'american samoa': 'AS',
  'northern mariana islands': 'MP',
  'u.s. virgin islands': 'VI',
  'virgin islands': 'VI',
};

const STATE_CODES = new Set(Object.values(US_STATES));
const FULL_STATE_NAMES = Object.keys(US_STATES).sort((a, b) => b.length - a.length);

const STREET_SUFFIXES = [
  'allee', 'alley', 'ally', 'aly', 'annex', 'anx', 'arcade', 'arc',
  'avenue', 'ave', 'av', 'bayoo', 'bayou', 'beach', 'bch', 'bend', 'bnd',
  'bluff', 'blf', 'bluffs', 'blfs', 'bottom', 'bot', 'btm', 'boulevard',
  'blvd', 'branch', 'br', 'bridge', 'brg', 'brook', 'brk', 'brooks', 'brks',
  'burg', 'bg', 'burgs', 'bgs', 'bypass', 'byp', 'camp', 'cp', 'canyon',
  'cyn', 'cape', 'cpe', 'causeway', 'cswy', 'center', 'ctr', 'centers', 'ctrs',
  'circle', 'cir', 'circles', 'cirs', 'cliff', 'clf', 'cliffs', 'clfs',
  'club', 'clb', 'common', 'cmn', 'commons', 'cmns', 'corner', 'cor',
  'corners', 'cors', 'course', 'crse', 'court', 'ct', 'courts', 'cts',
  'cove', 'cv', 'coves', 'cvs', 'creek', 'crk', 'crescent', 'cres',
  'crest', 'crst', 'crossing', 'xing', 'crossroad', 'xrd', 'crossroads', 'xrds',
  'curve', 'curv', 'dale', 'dl', 'dam', 'dm', 'divide', 'div', 'dv',
  'drive', 'dr', 'drives', 'drs', 'estate', 'est', 'estates', 'ests',
  'expressway', 'expy', 'extension', 'ext', 'extensions', 'exts', 'fall',
  'falls', 'fls', 'ferry', 'fry', 'field', 'fld', 'fields', 'flds',
  'flat', 'flt', 'flats', 'flts', 'ford', 'frd', 'fords', 'frds',
  'forest', 'frst', 'forge', 'frg', 'forges', 'frgs', 'fork', 'frk',
  'forks', 'frks', 'fort', 'ft', 'freeway', 'fwy', 'garden', 'gdn',
  'gardens', 'gdns', 'gateway', 'gtwy', 'glen', 'gln', 'glens', 'glns',
  'green', 'grn', 'greens', 'grns', 'grove', 'grv', 'groves', 'grvs',
  'harbor', 'hbr', 'harbors', 'hbrs', 'haven', 'hvn', 'heights', 'hts',
  'highway', 'hwy', 'hill', 'hl', 'hills', 'hls', 'hollow', 'holw',
  'inlet', 'inlt', 'island', 'is', 'islands', 'iss', 'isle', 'junction',
  'jct', 'junctions', 'jcts', 'key', 'ky', 'keys', 'kys', 'knoll', 'knl',
  'knolls', 'knls', 'lake', 'lk', 'lakes', 'lks', 'land', 'landing',
  'lndg', 'lane', 'ln', 'light', 'lgt', 'lights', 'lgts', 'loaf', 'lf',
  'lock', 'lck', 'locks', 'lcks', 'lodge', 'ldg', 'loop', 'mall', 'manor',
  'mnr', 'manors', 'mnrs', 'meadow', 'mdw', 'meadows', 'mdws', 'mews',
  'mill', 'ml', 'mills', 'mls', 'mission', 'msn', 'motorway', 'mtwy',
  'mount', 'mt', 'mountain', 'mtn', 'mountains', 'mtns', 'neck', 'nck',
  'orchard', 'orch', 'oval', 'overpass', 'opas', 'park', 'parks', 'prk',
  'parkway', 'pkwy', 'parkways', 'pkwys', 'pass', 'passage', 'path',
  'pike', 'pine', 'pnes', 'pines', 'place', 'pl', 'plain', 'pln', 'plains',
  'plns', 'plaza', 'plz', 'point', 'pt', 'points', 'pts', 'port', 'prt',
  'ports', 'prts', 'prairie', 'pr', 'radial', 'radl', 'ramp', 'ranch',
  'rnch', 'rapids', 'rpds', 'rest', 'rst', 'ridge', 'rdg', 'ridges',
  'rdgs', 'river', 'riv', 'road', 'rd', 'roads', 'rds', 'route', 'rte',
  'row', 'rue', 'run', 'shoal', 'shl', 'shoals', 'shls', 'shore', 'shr',
  'shores', 'shrs', 'skyway', 'skwy', 'spring', 'spg', 'springs', 'spgs',
  'spur', 'square', 'sq', 'squares', 'sqs', 'station', 'sta', 'stravenue',
  'strav', 'stream', 'strm', 'street', 'st', 'streets', 'sts', 'summit',
  'smt', 'terrace', 'ter', 'throughway', 'trwy', 'trace', 'trce', 'track',
  'trak', 'trafficway', 'trfy', 'trail', 'trl', 'trailer', 'trlr',
  'tunnel', 'tunl', 'turnpike', 'tpke', 'underpass', 'upas', 'union',
  'un', 'unions', 'uns', 'valley', 'vly', 'valleys', 'vlys', 'viaduct',
  'via', 'vduct', 'view', 'vw', 'views', 'vws', 'village', 'vlg',
  'villages', 'vlgs', 'ville', 'vl', 'vista', 'vis', 'walk', 'walks',
  'wall', 'way', 'ways', 'well', 'wl', 'wells', 'wls'
];

/**
 * Parses a single address input string (e.g. postal code or full address)
 * into an Address object meeting backend requirements.
 */
export function parseAddress(input: string | Address): Address {
  if (typeof input === 'object' && input !== null) {
    return {
      street: (input.street || '').trim(),
      city: (input.city || '').trim(),
      state: (input.state || '').trim(),
      zipCode: (input.zipCode || '').trim(),
      ...(input.latitude != null ? { latitude: input.latitude } : {}),
      ...(input.longitude != null ? { longitude: input.longitude } : {}),
    };
  }

  const trimmed = (input || '').trim();
  if (!trimmed) {
    return { street: '', city: '', state: '', zipCode: '' };
  }

  // Check for direct coordinates "lat, lon"
  const coordMatch = trimmed.match(/^(-?\d{1,3}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)$/);
  if (coordMatch) {
    const lat = Number(coordMatch[1]);
    const lon = Number(coordMatch[2]);
    if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
      return {
        street: '',
        city: '',
        state: '',
        zipCode: '',
        latitude: lat,
        longitude: lon,
      };
    }
  }

  // 1. Pure zip code: 5 digits, or 9 digits (with or without hyphen)
  const pureZipMatch = trimmed.match(/^(\d{5})(?:-?(\d{4}))?$/);
  if (pureZipMatch) {
    const zipCode = pureZipMatch[2] ? `${pureZipMatch[1]}-${pureZipMatch[2]}` : pureZipMatch[1];
    return { street: '', city: '', state: '', zipCode };
  }

  // 2. Extract zip code from string (preferably at end)
  let zipCode = '';
  let textBeforeZip = trimmed;

  const zipAtEnd = trimmed.match(/(?:,\s*|\s+)(\d{5})(?:-(\d{4})|\s*(\d{4}))?\s*$/);
  const zip9AtEnd = trimmed.match(/(?:,\s*|\s+)(\d{5})(\d{4})\s*$/);

  if (zipAtEnd && zipAtEnd.index !== undefined) {
    const plus4 = zipAtEnd[2] || zipAtEnd[3];
    zipCode = plus4 ? `${zipAtEnd[1]}-${plus4}` : zipAtEnd[1];
    textBeforeZip = trimmed.slice(0, zipAtEnd.index).trim().replace(/,\s*$/, '');
  } else if (zip9AtEnd && zip9AtEnd.index !== undefined) {
    zipCode = `${zip9AtEnd[1]}-${zip9AtEnd[2]}`;
    textBeforeZip = trimmed.slice(0, zip9AtEnd.index).trim().replace(/,\s*$/, '');
  } else {
    const zipAnywhere = trimmed.match(/\b(\d{5})(?:-(\d{4}))?\b/);
    if (zipAnywhere && zipAnywhere.index !== undefined) {
      zipCode = zipAnywhere[2] ? `${zipAnywhere[1]}-${zipAnywhere[2]}` : zipAnywhere[1];
      textBeforeZip = (
        trimmed.slice(0, zipAnywhere.index) + ' ' + trimmed.slice(zipAnywhere.index + zipAnywhere[0].length)
      ).trim().replace(/,\s*,/g, ',').replace(/^,\s*|,\s*$/g, '');
    }
  }

  // 3. Extract state from textBeforeZip (preferably at end)
  let state = '';
  let textBeforeState = textBeforeZip;

  const stateCodeMatch = textBeforeZip.match(/(?:,\s*|\s+)([a-zA-Z]{2})\s*$/);
  if (stateCodeMatch && STATE_CODES.has(stateCodeMatch[1].toUpperCase()) && stateCodeMatch.index !== undefined) {
    state = stateCodeMatch[1].toUpperCase();
    textBeforeState = textBeforeZip.slice(0, stateCodeMatch.index).trim().replace(/,\s*$/, '');
  } else {
    for (const name of FULL_STATE_NAMES) {
      const regex = new RegExp(`(?:,\\s*|\\s+|^)${name}\\s*$`, 'i');
      const match = textBeforeZip.match(regex);
      if (match && match.index !== undefined) {
        state = US_STATES[name];
        textBeforeState = textBeforeZip.slice(0, match.index).trim().replace(/,\s*$/, '');
        break;
      }
    }
  }

  // 4. Distinguish street and city from textBeforeState
  let street = '';
  let city = '';

  if (textBeforeState.includes(',')) {
    const parts = textBeforeState.split(',').map(p => p.trim()).filter(Boolean);
    if (parts.length >= 2) {
      city = parts[parts.length - 1];
      street = parts.slice(0, -1).join(', ');
    } else if (parts.length === 1) {
      const single = parts[0];
      if (/^\d/.test(single) || /^(p\.?o\.?\s*box)/i.test(single)) {
        street = single;
      } else {
        city = single;
      }
    }
  } else if (textBeforeState) {
    if (/^\d/.test(textBeforeState) || /^(p\.?o\.?\s*box)/i.test(textBeforeState)) {
      const suffixRegex = new RegExp(`\\b(?:${STREET_SUFFIXES.join('|')})\\.?\\s+`, 'i');
      const suffixMatch = textBeforeState.match(suffixRegex);
      if (suffixMatch && suffixMatch.index !== undefined) {
        const splitPos = suffixMatch.index + suffixMatch[0].length;
        const potentialStreet = textBeforeState.slice(0, splitPos).trim();
        const potentialCity = textBeforeState.slice(splitPos).trim();
        const unitMatch = potentialCity.match(
          /^(?:apt\.?|apartment|suite|ste\.?|unit|bldg\.?|floor|fl\.?|rm\.?|room|#)\s*[\w-]+\s+/i
        );
        if (unitMatch) {
          street = `${potentialStreet} ${potentialCity.slice(0, unitMatch[0].length).trim()}`;
          city = potentialCity.slice(unitMatch[0].length).trim();
        } else {
          street = potentialStreet;
          city = potentialCity;
        }
      } else {
        const words = textBeforeState.split(/\s+/);
        if (words.length > 2 && state) {
          city = words[words.length - 1];
          street = words.slice(0, -1).join(' ');
        } else {
          street = textBeforeState;
        }
      }
    } else {
      city = textBeforeState;
    }
  }

  return {
    street,
    city,
    state,
    zipCode,
  };
}
