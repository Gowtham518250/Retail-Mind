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
