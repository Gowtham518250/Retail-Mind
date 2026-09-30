'use client';

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

type LanguageCode = 'en' | 'te' | 'hi' | 'ta';

type LanguageContextValue = {
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
  t: (key: string, fallback?: string) => string;
  languages: { code: LanguageCode; nativeName: string; name: string }[];
};

const languages: LanguageContextValue['languages'] = [
  { code: 'en', nativeName: 'English', name: 'English' },
  { code: 'te', nativeName: 'తెలుగు', name: 'Telugu' },
  { code: 'hi', nativeName: 'हिन्दी', name: 'Hindi' },
  { code: 'ta', nativeName: 'தமிழ்', name: 'Tamil' },
];

const translations: Record<LanguageCode, Record<string, string>> = {
  en: {
    nav_orders: 'Orders',
    nav_profile: 'Profile',
    nav_cart: 'Cart',
    nav_language: 'Language',
    orders_title: 'My Orders',
    orders_live: 'Live order updates enabled',
    orders_refresh: 'Refresh',
    orders_back: 'Back',
    orders_start: 'Start shopping',
    orders_empty_title: 'Your order space is ready',
    orders_empty_text: 'Place your first order and follow every stage from confirmation to delivery here.',
    status_PENDING: 'Order placed',
    status_ACCEPTED: 'Order accepted',
    status_DISPATCHED: 'Out for delivery',
    status_DELIVERED: 'Delivered',
    status_REJECTED: 'Order rejected',
    status_PENDING_desc: 'Your order is waiting for the shop to confirm it.',
    status_ACCEPTED_desc: 'The shop has accepted your order and will prepare it.',
    status_DISPATCHED_desc: 'Your order has been dispatched from the shop.',
    status_DELIVERED_desc: 'Your order has been marked as delivered.',
    status_REJECTED_desc: 'The shop could not fulfil this order.',
    delivery_address: 'Delivery address',
    total: 'Total',

    store_premium: 'Premium local storefront',
    store_tagline: 'Discover fresh essentials, daily deals, and a delightful shopping experience built for modern customers.',
    store_secure: 'Secure checkout',
    store_fast: 'Fast dispatch',
    store_shop: 'Shop now',
    store_search: 'Search by product, category or keyword',
    store_featured: 'Featured',
    store_low: 'Price: Low to High',
    store_high: 'Price: High to Low',
    store_discount: 'Best discount',
    store_curated: 'Curated for you',
    store_popular: 'Popular picks',
    store_no_results: 'No products match your search yet. Try another keyword.',

    cart_title: 'Your Cart',
    cart_empty: 'Your cart is empty',
    cart_add_start: 'Add items from the store to get started',
    cart_subtotal: 'Subtotal',
    cart_note: 'Taxes included. Delivery charges calculated at checkout.',
    cart_checkout: 'Proceed to Checkout',
    product_off: 'OFF',
    product_out: 'Out of stock',
    product_in: 'In stock',
    product_featured: 'Featured',
    product_desc: 'Freshly curated for your daily essentials.',
    product_left: 'left',
    product_ready: 'Ready to ship',
    product_added: 'Added',
    product_in_cart: 'In cart',
    product_add: 'Add to cart',
    product_view: 'View',
  },
  te: {
    nav_orders: 'ఆర్డర్లు',
    nav_profile: 'ప్రొఫైల్',
    nav_cart: 'కార్ట్',
    nav_language: 'భాష',
    orders_title: 'నా ఆర్డర్లు',
    orders_live: 'లైవ్ ఆర్డర్ అప్‌డేట్స్ ఆన్‌లో ఉన్నాయి',
    orders_refresh: 'రిఫ్రెష్',
    orders_back: 'వెనుకకు',
    orders_start: 'షాపింగ్ ప్రారంభించండి',
    orders_empty_title: 'మీ ఆర్డర్ల కోసం స్థలం సిద్ధంగా ఉంది',
    orders_empty_text: 'మొదటి ఆర్డర్ చేసి కన్ఫర్మ్ నుంచి డెలివరీ వరకు ప్రతి దశను ఇక్కడ చూడండి.',
    status_PENDING: 'ఆర్డర్ నమోదు అయింది',
    status_ACCEPTED: 'ఆర్డర్ ఆమోదించబడింది',
    status_DISPATCHED: 'డెలివరీకి పంపబడింది',
    status_DELIVERED: 'డెలివరీ అయింది',
    status_REJECTED: 'ఆర్డర్ తిరస్కరించబడింది',
    status_PENDING_desc: 'షాప్ మీ ఆర్డర్‌ను కన్ఫర్మ్ చేయడానికి వేచి ఉంది.',
    status_ACCEPTED_desc: 'షాప్ ఆర్డర్‌ను ఆమోదించి సిద్ధం చేస్తోంది.',
    status_DISPATCHED_desc: 'మీ ఆర్డర్ షాప్ నుంచి బయలుదేరింది.',
    status_DELIVERED_desc: 'మీ ఆర్డర్ డెలివర్ అయింది.',
    status_REJECTED_desc: 'షాప్ ఈ ఆర్డర్‌ను పూర్తి చేయలేకపోయింది.',
    delivery_address: 'డెలివరీ చిరునామా',
    total: 'మొత్తం',

    store_premium: 'ప్రీమియం స్థానిక స్టోర్',
    store_tagline: 'తాజా అవసరాలు, రోజువారీ ఆఫర్లు మరియు సులభమైన షాపింగ్ అనుభవాన్ని పొందండి.',
    store_secure: 'సురక్షిత చెకౌట్',
    store_fast: 'వేగవంతమైన డిస్పాచ్',
    store_shop: 'ఇప్పుడే కొనండి',
    store_search: 'ఉత్పత్తి, కేటగిరీ లేదా కీవర్డ్‌తో వెతకండి',
    store_featured: 'ఫీచర్డ్',
    store_low: 'ధర: తక్కువ నుంచి ఎక్కువ',
    store_high: 'ధర: ఎక్కువ నుంచి తక్కువ',
    store_discount: 'ఉత్తమ డిస్కౌంట్',
    store_curated: 'మీ కోసం ఎంపిక',
    store_popular: 'ప్రముఖ ఎంపికలు',
    store_no_results: 'మీ శోధనకు సరిపోయే ఉత్పత్తులు లేవు.',

    cart_title: 'మీ కార్ట్',
    cart_empty: 'మీ కార్ట్ ఖాళీగా ఉంది',
    cart_add_start: 'ప్రారంభించడానికి స్టోర్ నుంచి ఉత్పత్తులు జోడించండి',
    cart_subtotal: 'ఉప మొత్తం',
    cart_note: 'పన్నులు చేర్చబడ్డాయి. డెలివరీ ఛార్జీలు చెకౌట్‌లో లెక్కించబడతాయి.',
    cart_checkout: 'చెకౌట్‌కు వెళ్లండి',
    product_off: 'ఆఫ్',
    product_out: 'స్టాక్ లేదు',
    product_in: 'స్టాక్‌లో ఉంది',
    product_featured: 'ఫీచర్డ్',
    product_desc: 'రోజువారీ అవసరాల కోసం ఎంపిక చేసిన ఉత్పత్తులు.',
    product_left: 'మిగిలాయి',
    product_ready: 'పంపడానికి సిద్ధంగా ఉంది',
    product_added: 'జోడించబడింది',
    product_in_cart: 'కార్ట్‌లో',
    product_add: 'కార్ట్‌కు జోడించండి',
    product_view: 'చూడండి',
  },
  hi: {
    nav_orders: 'ऑर्डर',
    nav_profile: 'प्रोफ़ाइल',
    nav_cart: 'कार्ट',
    nav_language: 'भाषा',
    orders_title: 'मेरे ऑर्डर',
    orders_live: 'लाइव ऑर्डर अपडेट चालू हैं',
    orders_refresh: 'रिफ्रेश',
    orders_back: 'वापस',
    orders_start: 'शॉपिंग शुरू करें',
    orders_empty_title: 'आपके ऑर्डर के लिए जगह तैयार है',
    orders_empty_text: 'पहला ऑर्डर करें और पुष्टि से डिलीवरी तक हर चरण यहां देखें।',
    status_PENDING: 'ऑर्डर किया गया',
    status_ACCEPTED: 'ऑर्डर स्वीकार किया गया',
    status_DISPATCHED: 'डिलीवरी के लिए भेजा गया',
    status_DELIVERED: 'डिलीवर हो गया',
    status_REJECTED: 'ऑर्डर अस्वीकार किया गया',
    status_PENDING_desc: 'दुकान आपके ऑर्डर की पुष्टि का इंतज़ार कर रही है।',
    status_ACCEPTED_desc: 'दुकान ने आपका ऑर्डर स्वीकार कर लिया है और तैयार कर रही है।',
    status_DISPATCHED_desc: 'आपका ऑर्डर दुकान से भेज दिया गया है।',
    status_DELIVERED_desc: 'आपका ऑर्डर डिलीवर हो गया है।',
    status_REJECTED_desc: 'दुकान यह ऑर्डर पूरा नहीं कर सकी।',
    delivery_address: 'डिलीवरी पता',
    total: 'कुल',

    store_premium: 'प्रीमियम स्थानीय स्टोर',
    store_tagline: 'ताज़ी आवश्यक वस्तुएं, रोज़ाना ऑफ़र और आसान शॉपिंग अनुभव पाएं।',
    store_secure: 'सुरक्षित चेकआउट',
    store_fast: 'तेज़ डिस्पैच',
    store_shop: 'अभी खरीदें',
    store_search: 'उत्पाद, श्रेणी या कीवर्ड से खोजें',
    store_featured: 'फ़ीचर्ड',
    store_low: 'कीमत: कम से अधिक',
    store_high: 'कीमत: अधिक से कम',
    store_discount: 'सर्वोत्तम छूट',
    store_curated: 'आपके लिए चुना गया',
    store_popular: 'लोकप्रिय विकल्प',
    store_no_results: 'आपकी खोज से मेल खाने वाले उत्पाद नहीं मिले।',

    cart_title: 'आपकी कार्ट',
    cart_empty: 'आपकी कार्ट खाली है',
    cart_add_start: 'शुरू करने के लिए स्टोर से सामान जोड़ें',
    cart_subtotal: 'उप-योग',
    cart_note: 'टैक्स शामिल हैं। डिलीवरी शुल्क चेकआउट पर लगेगा।',
    cart_checkout: 'चेकआउट पर जाएं',
    product_off: 'ऑफ',
    product_out: 'स्टॉक खत्म',
    product_in: 'स्टॉक में',
    product_featured: 'फीचर्ड',
    product_desc: 'आपकी रोज़मर्रा की ज़रूरतों के लिए चुना गया।',
    product_left: 'बाकी',
    product_ready: 'भेजने के लिए तैयार',
    product_added: 'जोड़ा गया',
    product_in_cart: 'कार्ट में',
    product_add: 'कार्ट में जोड़ें',
    product_view: 'देखें',
  },
  ta: {
    nav_orders: 'ஆர்டர்கள்',
    nav_profile: 'சுயவிவரம்',
    nav_cart: 'கார்ட்',
    nav_language: 'மொழி',
    orders_title: 'என் ஆர்டர்கள்',
    orders_live: 'நேரடி ஆர்டர் புதுப்பிப்புகள் இயங்குகின்றன',
    orders_refresh: 'புதுப்பி',
    orders_back: 'பின்',
    orders_start: 'ஷாப்பிங் தொடங்கு',
    orders_empty_title: 'உங்கள் ஆர்டர்களுக்கான பகுதி தயார்',
    orders_empty_text: 'முதல் ஆர்டரை செய்து உறுதிப்படுத்தல் முதல் டெலிவரி வரை ஒவ்வொரு நிலையும் இங்கே காணுங்கள்.',
    status_PENDING: 'ஆர்டர் செய்யப்பட்டது',
    status_ACCEPTED: 'ஆர்டர் ஏற்கப்பட்டது',
    status_DISPATCHED: 'டெலிவரிக்கு அனுப்பப்பட்டது',
    status_DELIVERED: 'டெலிவரி முடிந்தது',
    status_REJECTED: 'ஆர்டர் நிராகரிக்கப்பட்டது',
    status_PENDING_desc: 'உங்கள் ஆர்டரை கடை உறுதிப்படுத்த காத்திருக்கிறது.',
    status_ACCEPTED_desc: 'கடை உங்கள் ஆர்டரை ஏற்று தயாரித்து வருகிறது.',
    status_DISPATCHED_desc: 'உங்கள் ஆர்டர் கடையிலிருந்து அனுப்பப்பட்டது.',
    status_DELIVERED_desc: 'உங்கள் ஆர்டர் டெலிவரி செய்யப்பட்டது.',
    status_REJECTED_desc: 'கடை இந்த ஆர்டரை நிறைவேற்ற முடியவில்லை.',
    delivery_address: 'டெலிவரி முகவரி',
    total: 'மொத்தம்',

    store_premium: 'பிரீமியம் உள்ளூர் கடை',
    store_tagline: 'புதிய அத்தியாவசியங்கள், தினசரி சலுகைகள் மற்றும் எளிய ஷாப்பிங் அனுபவம்.',
    store_secure: 'பாதுகாப்பான செக்அவுட்',
    store_fast: 'வேகமான அனுப்பல்',
    store_shop: 'இப்போது வாங்குங்கள்',
    store_search: 'பொருள், வகை அல்லது முக்கிய சொல்லால் தேடுங்கள்',
    store_featured: 'சிறப்பு',
    store_low: 'விலை: குறைவிலிருந்து அதிகம்',
    store_high: 'விலை: அதிகத்திலிருந்து குறைவு',
    store_discount: 'சிறந்த தள்ளுபடி',
    store_curated: 'உங்களுக்காக தேர்வு',
    store_popular: 'பிரபலமான தேர்வுகள்',
    store_no_results: 'உங்கள் தேடலுக்கு பொருத்தமான பொருட்கள் இல்லை.',

    cart_title: 'உங்கள் கார்ட்',
    cart_empty: 'உங்கள் கார்ட் காலியாக உள்ளது',
    cart_add_start: 'தொடங்க கடையிலிருந்து பொருட்களை சேர்க்கவும்',
    cart_subtotal: 'கூட்டுத்தொகை',
    cart_note: 'வரி சேர்க்கப்பட்டுள்ளது. டெலிவரி கட்டணம் செக்அவுட்டில் கணக்கிடப்படும்.',
    cart_checkout: 'செக்அவுட்டுக்கு செல்லவும்',
    product_off: 'தள்ளுபடி',
    product_out: 'ஸ்டாக் இல்லை',
    product_in: 'ஸ்டாக் உள்ளது',
    product_featured: 'சிறப்பு',
    product_desc: 'உங்கள் தினசரி தேவைகளுக்காக தேர்வு செய்யப்பட்டது.',
    product_left: 'மீதம்',
    product_ready: 'அனுப்ப தயார்',
    product_added: 'சேர்க்கப்பட்டது',
    product_in_cart: 'கார்ட்டில்',
    product_add: 'கார்ட்டில் சேர்க்கவும்',
    product_view: 'பார்க்க',
  },
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<LanguageCode>('en');

  useEffect(() => {
    const saved = localStorage.getItem('retailmind:web-language') as LanguageCode | null;
    if (saved && languages.some((entry) => entry.code === saved)) {
      setLanguageState(saved);
    }
  }, []);

  const setLanguage = (next: LanguageCode) => {
    setLanguageState(next);
    localStorage.setItem('retailmind:web-language', next);
    document.documentElement.lang = next;
  };

  const value = useMemo<LanguageContextValue>(() => ({
    language,
    setLanguage,
    languages,
    t: (key, fallback) => translations[language][key] ?? translations.en[key] ?? fallback ?? key,
  }), [language]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useLanguage must be used inside LanguageProvider');
  return context;
}
