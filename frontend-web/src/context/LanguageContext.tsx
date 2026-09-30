'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

export type WebLanguage = 'en' | 'te' | 'hi' | 'ta' | 'kn' | 'ml' | 'mr' | 'gu' | 'bn' | 'pa';

const translations = {
  en: {
    brand: 'RetailShop', orders: 'Orders', profile: 'Profile', cart: 'Cart',
    signIn: 'Sign In', welcomeBack: 'Welcome back', signInContinue: 'Sign in to continue shopping',
    createAccount: 'Create account', newHere: 'New here?', createNewAccount: 'Create an account',
    alreadyMember: 'Already a member?', password: 'Password', email: 'Email', phone: 'Mobile Number',
    fullName: 'Full Name', forgotPassword: 'Forgot password?', resetPassword: 'Reset password',
    sendNewPassword: 'Send New Password', backToSignIn: 'Back to Sign In',
    myOrders: 'My Orders', customerAccount: 'Customer account',
    trackEveryOrder: 'Track every order, status change, delivery step and item in one place.',
    liveUpdates: 'Live updates', fallbackSync: 'Fallback sync', refresh: 'Refresh', back: 'Back',
    syncing: 'Syncing…', updated: 'Updated', startShopping: 'Start shopping',
    noOrders: 'No orders yet', ordersEmpty: 'Your placed orders will appear here with live status updates.',
    couldntLoadOrders: "Couldn't load your orders", tryAgain: 'Try again',
    orderPlaced: 'Order placed', orderPlacedDesc: 'Waiting for the shop to accept your order.',
    acceptedPreparing: 'Accepted & preparing', acceptedPreparingDesc: 'The shop accepted your order and is preparing it.',
    outForDelivery: 'Out for delivery', outForDeliveryDesc: 'Your order has been dispatched.',
    delivered: 'Delivered', deliveredDesc: 'Order completed successfully.',
    rejected: 'Order rejected', rejectedDesc: 'The shop could not fulfill this order.',
    items: 'Items', qty: 'Qty', deliveryAddress: 'Delivery address', total: 'Total',
    trackOrder: 'Track order', continueShopping: 'Continue shopping',
    yourCart: 'Your Cart', cartEmpty: 'Your cart is empty',
    addItems: 'Add items from the store to get started', subtotal: 'Subtotal',
    delivery: 'Delivery', free: 'FREE', gst: 'GST', included: 'Included',
    proceedCheckout: 'Proceed to Checkout', searchProducts: 'Search by product, category or keyword',
    popularPicks: 'Popular picks', curatedForYou: 'Curated for you', shopNow: 'Shop now',
    secureCheckout: 'Secure checkout', fastDispatch: 'Fast dispatch', products: 'products',
    checkout: 'Checkout', deliveryDetails: 'Delivery details', address: 'Address',
    city: 'City', pincode: 'Pincode', landmark: 'Landmark', optional: 'optional',
    orderNotes: 'Order notes', detectLocation: 'Detect location', paymentMethod: 'Payment method',
    cashOnDelivery: 'Cash on Delivery', payWhenArrives: 'Pay when your order arrives',
    placeOrder: 'Place Order', placingOrder: 'Placing order…', orderSummary: 'Order summary',
    secureGuestCheckout: 'Secure guest checkout · No account needed', orderSuccess: 'Order placed successfully!',
    liveOrderStatus: 'Live order status', downloadInvoice: 'Download invoice',
    estimatedDelivery: 'Estimated delivery', payment: 'Payment',
    signOut: 'Sign out', language: 'Language',
  },
  te: {
    brand: 'రిటైల్‌షాప్', orders: 'ఆర్డర్లు', profile: 'ప్రొఫైల్', cart: 'కార్ట్',
    signIn: 'సైన్ ఇన్', welcomeBack: 'తిరిగి స్వాగతం', signInContinue: 'షాపింగ్ కొనసాగించడానికి సైన్ ఇన్ చేయండి',
    createAccount: 'ఖాతా సృష్టించండి', newHere: 'కొత్తగా వచ్చారా?', createNewAccount: 'ఖాతా సృష్టించండి',
    alreadyMember: 'ఇప్పటికే సభ్యులా?', password: 'పాస్‌వర్డ్', email: 'ఈమెయిల్', phone: 'మొబైల్ నంబర్',
    fullName: 'పూర్తి పేరు', forgotPassword: 'పాస్‌వర్డ్ మర్చిపోయారా?', resetPassword: 'పాస్‌వర్డ్ రీసెట్',
    sendNewPassword: 'కొత్త పాస్‌వర్డ్ పంపండి', backToSignIn: 'సైన్ ఇన్‌కు తిరిగి వెళ్లండి',
    myOrders: 'నా ఆర్డర్లు', customerAccount: 'కస్టమర్ ఖాతా',
    trackEveryOrder: 'ప్రతి ఆర్డర్, స్థితి, డెలివరీ దశను ఒకే చోట చూడండి.',
    liveUpdates: 'లైవ్ అప్‌డేట్లు', fallbackSync: 'ఫాల్‌బ్యాక్ సింక్', refresh: 'రిఫ్రెష్', back: 'వెనుకకు',
    syncing: 'సింక్ అవుతోంది…', updated: 'అప్‌డేట్', startShopping: 'షాపింగ్ ప్రారంభించండి',
    noOrders: 'ఇంకా ఆర్డర్లు లేవు', ordersEmpty: 'మీ ఆర్డర్లు ఇక్కడ లైవ్ స్థితితో కనిపిస్తాయి.',
    couldntLoadOrders: 'ఆర్డర్లను లోడ్ చేయలేకపోయాం', tryAgain: 'మళ్లీ ప్రయత్నించండి',
    orderPlaced: 'ఆర్డర్ పెట్టబడింది', orderPlacedDesc: 'షాప్ మీ ఆర్డర్‌ను అంగీకరించే వరకు వేచి ఉంది.',
    acceptedPreparing: 'అంగీకరించబడింది & సిద్ధమవుతోంది', acceptedPreparingDesc: 'షాప్ మీ ఆర్డర్‌ను అంగీకరించి సిద్ధం చేస్తోంది.',
    outForDelivery: 'డెలివరీకి బయలుదేరింది', outForDeliveryDesc: 'మీ ఆర్డర్ పంపబడింది.',
    delivered: 'డెలివరీ అయింది', deliveredDesc: 'ఆర్డర్ విజయవంతంగా పూర్తయింది.',
    rejected: 'ఆర్డర్ తిరస్కరించబడింది', rejectedDesc: 'షాప్ ఈ ఆర్డర్‌ను పూర్తి చేయలేకపోయింది.',
    items: 'వస్తువులు', qty: 'పరిమాణం', deliveryAddress: 'డెలివరీ చిరునామా', total: 'మొత్తం',
    trackOrder: 'ఆర్డర్ ట్రాక్ చేయండి', continueShopping: 'షాపింగ్ కొనసాగించండి',
    yourCart: 'మీ కార్ట్', cartEmpty: 'మీ కార్ట్ ఖాళీగా ఉంది',
    addItems: 'కొనసాగడానికి షాప్ నుంచి వస్తువులు జోడించండి', subtotal: 'ఉపమొత్తం',
    delivery: 'డెలివరీ', free: 'ఉచితం', gst: 'GST', included: 'చేర్చబడింది',
    proceedCheckout: 'చెక్‌అవుట్‌కు వెళ్లండి', searchProducts: 'ఉత్పత్తి, వర్గం లేదా పదంతో శోధించండి',
    popularPicks: 'పాపులర్ ఉత్పత్తులు', curatedForYou: 'మీ కోసం ఎంపిక చేసినవి', shopNow: 'ఇప్పుడే షాప్ చేయండి',
    secureCheckout: 'సురక్షిత చెక్‌అవుట్', fastDispatch: 'త్వరిత పంపకం', products: 'ఉత్పత్తులు',
    checkout: 'చెక్‌అవుట్', deliveryDetails: 'డెలివరీ వివరాలు', address: 'చిరునామా',
    city: 'నగరం', pincode: 'పిన్‌కోడ్', landmark: 'ల్యాండ్‌మార్క్', optional: 'ఐచ్ఛికం',
    orderNotes: 'ఆర్డర్ గమనికలు', detectLocation: 'స్థానాన్ని గుర్తించండి', paymentMethod: 'చెల్లింపు విధానం',
    cashOnDelivery: 'క్యాష్ ఆన్ డెలివరీ', payWhenArrives: 'ఆర్డర్ వచ్చినప్పుడు చెల్లించండి',
    placeOrder: 'ఆర్డర్ పెట్టండి', placingOrder: 'ఆర్డర్ పెట్టబడుతోంది…', orderSummary: 'ఆర్డర్ సారాంశం',
    secureGuestCheckout: 'సురక్షిత గెస్ట్ చెక్‌అవుట్ · ఖాతా అవసరం లేదు', orderSuccess: 'ఆర్డర్ విజయవంతంగా పెట్టబడింది!',
    liveOrderStatus: 'లైవ్ ఆర్డర్ స్థితి', downloadInvoice: 'ఇన్వాయిస్ డౌన్‌లోడ్',
    estimatedDelivery: 'అంచనా డెలివరీ', payment: 'చెల్లింపు',
    signOut: 'సైన్ అవుట్', language: 'భాష',
  },
  hi: {
    brand: 'रिटेलशॉप', orders: 'ऑर्डर', profile: 'प्रोफ़ाइल', cart: 'कार्ट',
    signIn: 'साइन इन', welcomeBack: 'वापसी पर स्वागत है', signInContinue: 'शॉपिंग जारी रखने के लिए साइन इन करें',
    createAccount: 'खाता बनाएं', newHere: 'यहाँ नए हैं?', createNewAccount: 'खाता बनाएं',
    alreadyMember: 'पहले से सदस्य हैं?', password: 'पासवर्ड', email: 'ईमेल', phone: 'मोबाइल नंबर',
    fullName: 'पूरा नाम', forgotPassword: 'पासवर्ड भूल गए?', resetPassword: 'पासवर्ड रीसेट',
    sendNewPassword: 'नया पासवर्ड भेजें', backToSignIn: 'साइन इन पर वापस जाएँ',
    myOrders: 'मेरे ऑर्डर', customerAccount: 'ग्राहक खाता',
    trackEveryOrder: 'हर ऑर्डर, स्टेटस और डिलीवरी चरण को एक ही जगह देखें।',
    liveUpdates: 'लाइव अपडेट', fallbackSync: 'फॉलबैक सिंक', refresh: 'रिफ्रेश', back: 'वापस',
    syncing: 'सिंक हो रहा है…', updated: 'अपडेट', startShopping: 'शॉपिंग शुरू करें',
    noOrders: 'अभी कोई ऑर्डर नहीं', ordersEmpty: 'आपके ऑर्डर यहाँ लाइव स्टेटस के साथ दिखेंगे।',
    couldntLoadOrders: 'ऑर्डर लोड नहीं हो सके', tryAgain: 'फिर कोशिश करें',
    orderPlaced: 'ऑर्डर किया गया', orderPlacedDesc: 'दुकान के स्वीकार करने की प्रतीक्षा है।',
    acceptedPreparing: 'स्वीकार किया गया और तैयार हो रहा है', acceptedPreparingDesc: 'दुकान आपका ऑर्डर तैयार कर रही है।',
    outForDelivery: 'डिलीवरी के लिए निकल गया', outForDeliveryDesc: 'आपका ऑर्डर भेज दिया गया है।',
    delivered: 'डिलीवर हो गया', deliveredDesc: 'ऑर्डर सफलतापूर्वक पूरा हुआ।',
    rejected: 'ऑर्डर अस्वीकार', rejectedDesc: 'दुकान यह ऑर्डर पूरा नहीं कर सकी।',
    items: 'वस्तुएँ', qty: 'मात्रा', deliveryAddress: 'डिलीवरी पता', total: 'कुल',
    trackOrder: 'ऑर्डर ट्रैक करें', continueShopping: 'शॉपिंग जारी रखें',
    yourCart: 'आपकी कार्ट', cartEmpty: 'आपकी कार्ट खाली है',
    addItems: 'शुरू करने के लिए सामान जोड़ें', subtotal: 'उप-योग',
    delivery: 'डिलीवरी', free: 'मुफ़्त', gst: 'GST', included: 'शामिल',
    proceedCheckout: 'चेकआउट पर जाएँ', searchProducts: 'उत्पाद, श्रेणी या शब्द से खोजें',
    popularPicks: 'लोकप्रिय उत्पाद', curatedForYou: 'आपके लिए चुने गए', shopNow: 'अभी खरीदें',
    secureCheckout: 'सुरक्षित चेकआउट', fastDispatch: 'तेज़ डिस्पैच', products: 'उत्पाद',
    checkout: 'चेकआउट', deliveryDetails: 'डिलीवरी विवरण', address: 'पता',
    city: 'शहर', pincode: 'पिनकोड', landmark: 'लैंडमार्क', optional: 'वैकल्पिक',
    orderNotes: 'ऑर्डर नोट्स', detectLocation: 'स्थान पहचानें', paymentMethod: 'भुगतान विधि',
    cashOnDelivery: 'कैश ऑन डिलीवरी', payWhenArrives: 'ऑर्डर मिलने पर भुगतान करें',
    placeOrder: 'ऑर्डर करें', placingOrder: 'ऑर्डर किया जा रहा है…', orderSummary: 'ऑर्डर सारांश',
    secureGuestCheckout: 'सुरक्षित गेस्ट चेकआउट · खाता आवश्यक नहीं', orderSuccess: 'ऑर्डर सफलतापूर्वक किया गया!',
    liveOrderStatus: 'लाइव ऑर्डर स्थिति', downloadInvoice: 'इनवॉइस डाउनलोड',
    estimatedDelivery: 'अनुमानित डिलीवरी', payment: 'भुगतान',
    signOut: 'साइन आउट', language: 'भाषा',
  },
  ta: {
    brand: 'ரீட்டெயில்ஷாப்', orders: 'ஆர்டர்கள்', profile: 'சுயவிவரம்', cart: 'கார்ட்',
    signIn: 'உள்நுழை', welcomeBack: 'மீண்டும் வரவேற்கிறோம்', signInContinue: 'ஷாப்பிங்கை தொடர உள்நுழையவும்',
    createAccount: 'கணக்கை உருவாக்கு', newHere: 'புதியவரா?', createNewAccount: 'கணக்கை உருவாக்கு',
    alreadyMember: 'ஏற்கனவே உறுப்பினரா?', password: 'கடவுச்சொல்', email: 'மின்னஞ்சல்', phone: 'மொபைல் எண்',
    fullName: 'முழு பெயர்', forgotPassword: 'கடவுச்சொல் மறந்துவிட்டீர்களா?', resetPassword: 'கடவுச்சொல் மீட்டமை',
    sendNewPassword: 'புதிய கடவுச்சொல் அனுப்பு', backToSignIn: 'உள்நுழைவுக்கு திரும்பு',
    myOrders: 'என் ஆர்டர்கள்', customerAccount: 'வாடிக்கையாளர் கணக்கு',
    trackEveryOrder: 'அனைத்து ஆர்டர்களையும் நிலை மற்றும் டெலிவரி படிகளுடன் ஒரே இடத்தில் பார்க்கவும்.',
    liveUpdates: 'நேரடி புதுப்பிப்புகள்', fallbackSync: 'மாற்று ஒத்திசைவு', refresh: 'புதுப்பி', back: 'பின்னால்',
    syncing: 'ஒத்திசைக்கிறது…', updated: 'புதுப்பிப்பு', startShopping: 'ஷாப்பிங் தொடங்கு',
    noOrders: 'இன்னும் ஆர்டர்கள் இல்லை', ordersEmpty: 'உங்கள் ஆர்டர்கள் நேரடி நிலை புதுப்பிப்புகளுடன் இங்கே தோன்றும்.',
    couldntLoadOrders: 'ஆர்டர்களை ஏற்ற முடியவில்லை', tryAgain: 'மீண்டும் முயற்சி',
    orderPlaced: 'ஆர்டர் செய்யப்பட்டது', orderPlacedDesc: 'கடை உங்கள் ஆர்டரை ஏற்க காத்திருக்கிறது.',
    acceptedPreparing: 'ஏற்கப்பட்டது & தயாராகிறது', acceptedPreparingDesc: 'கடை உங்கள் ஆர்டரை தயாரிக்கிறது.',
    outForDelivery: 'டெலிவரிக்கு புறப்பட்டது', outForDeliveryDesc: 'உங்கள் ஆர்டர் அனுப்பப்பட்டது.',
    delivered: 'டெலிவரி முடிந்தது', deliveredDesc: 'ஆர்டர் வெற்றிகரமாக முடிந்தது.',
    rejected: 'ஆர்டர் நிராகரிக்கப்பட்டது', rejectedDesc: 'கடை இந்த ஆர்டரை நிறைவேற்ற முடியவில்லை.',
    items: 'பொருட்கள்', qty: 'அளவு', deliveryAddress: 'டெலிவரி முகவரி', total: 'மொத்தம்',
    trackOrder: 'ஆர்டரை கண்காணி', continueShopping: 'ஷாப்பிங்கை தொடரு',
    yourCart: 'உங்கள் கார்ட்', cartEmpty: 'உங்கள் கார்ட் காலியாக உள்ளது',
    addItems: 'தொடங்க கடையிலிருந்து பொருட்களை சேர்க்கவும்', subtotal: 'கூட்டுத்தொகை',
    delivery: 'டெலிவரி', free: 'இலவசம்', gst: 'GST', included: 'சேர்க்கப்பட்டது',
    proceedCheckout: 'செக்அவுட்டுக்கு செல்க', searchProducts: 'பொருள், வகை அல்லது சொல்லால் தேடுங்கள்',
    popularPicks: 'பிரபலமான பொருட்கள்', curatedForYou: 'உங்களுக்காக தேர்ந்தெடுக்கப்பட்டது', shopNow: 'இப்போது வாங்கு',
    secureCheckout: 'பாதுகாப்பான செக்அவுட்', fastDispatch: 'விரைவு அனுப்பல்', products: 'பொருட்கள்',
    checkout: 'செக்அவுட்', deliveryDetails: 'டெலிவரி விவரங்கள்', address: 'முகவரி',
    city: 'நகரம்', pincode: 'பின்கோடு', landmark: 'அடையாளம்', optional: 'விருப்பம்',
    orderNotes: 'ஆர்டர் குறிப்புகள்', detectLocation: 'இருப்பிடத்தை கண்டறி', paymentMethod: 'பணம் செலுத்தும் முறை',
    cashOnDelivery: 'கேஷ் ஆன் டெலிவரி', payWhenArrives: 'ஆர்டர் வந்தபோது செலுத்துங்கள்',
    placeOrder: 'ஆர்டர் செய்', placingOrder: 'ஆர்டர் செய்கிறது…', orderSummary: 'ஆர்டர் சுருக்கம்',
    secureGuestCheckout: 'பாதுகாப்பான கெஸ்ட் செக்அவுட் · கணக்கு தேவையில்லை', orderSuccess: 'ஆர்டர் வெற்றிகரமாக செய்யப்பட்டது!',
    liveOrderStatus: 'நேரடி ஆர்டர் நிலை', downloadInvoice: 'இன்வாய்ஸை பதிவிறக்கு',
    estimatedDelivery: 'மதிப்பிடப்பட்ட டெலிவரி', payment: 'பணம் செலுத்தல்',
    signOut: 'வெளியேறு', language: 'மொழி',
  },
  kn: {
    orders: 'ಆರ್ಡರ್‌ಗಳು', profile: 'ಪ್ರೊಫೈಲ್', cart: 'ಕಾರ್ಟ್', signIn: 'ಸೈನ್ ಇನ್',
    welcomeBack: 'ಮತ್ತೆ ಸ್ವಾಗತ', createAccount: 'ಖಾತೆ ರಚಿಸಿ', password: 'ಪಾಸ್‌ವರ್ಡ್',
    email: 'ಇಮೇಲ್', phone: 'ಮೊಬೈಲ್ ಸಂಖ್ಯೆ', fullName: 'ಪೂರ್ಣ ಹೆಸರು',
    myOrders: 'ನನ್ನ ಆರ್ಡರ್‌ಗಳು', customerAccount: 'ಗ್ರಾಹಕ ಖಾತೆ', liveUpdates: 'ಲೈವ್ ಅಪ್‌ಡೇಟ್‌ಗಳು',
    refresh: 'ರಿಫ್ರೆಶ್', back: 'ಹಿಂದಕ್ಕೆ', startShopping: 'ಶಾಪಿಂಗ್ ಪ್ರಾರಂಭಿಸಿ',
    noOrders: 'ಇನ್ನೂ ಆರ್ಡರ್‌ಗಳಿಲ್ಲ', orderPlaced: 'ಆರ್ಡರ್ ಮಾಡಲಾಗಿದೆ',
    acceptedPreparing: 'ಸ್ವೀಕರಿಸಲಾಗಿದೆ ಮತ್ತು ಸಿದ್ಧವಾಗುತ್ತಿದೆ', outForDelivery: 'ಡೆಲಿವರಿಗೆ ಹೊರಟಿದೆ',
    delivered: 'ತಲುಪಿಸಲಾಗಿದೆ', rejected: 'ಆರ್ಡರ್ ತಿರಸ್ಕರಿಸಲಾಗಿದೆ', items: 'ವಸ್ತುಗಳು',
    qty: 'ಪ್ರಮಾಣ', deliveryAddress: 'ಡೆಲಿವರಿ ವಿಳಾಸ', total: 'ಒಟ್ಟು', trackOrder: 'ಆರ್ಡರ್ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ',
    yourCart: 'ನಿಮ್ಮ ಕಾರ್ಟ್', cartEmpty: 'ನಿಮ್ಮ ಕಾರ್ಟ್ ಖಾಲಿಯಾಗಿದೆ', proceedCheckout: 'ಚೆಕ್‌ಔಟ್‌ಗೆ ಹೋಗಿ',
    language: 'ಭಾಷೆ',
  },
  ml: {
    orders: 'ഓർഡറുകൾ', profile: 'പ്രൊഫൈൽ', cart: 'കാർട്ട്', signIn: 'സൈൻ ഇൻ',
    welcomeBack: 'വീണ്ടും സ്വാഗതം', createAccount: 'അക്കൗണ്ട് സൃഷ്ടിക്കുക', password: 'പാസ്‌വേഡ്',
    email: 'ഇമെയിൽ', phone: 'മൊബൈൽ നമ്പർ', fullName: 'പൂർണ്ണ പേര്',
    myOrders: 'എന്റെ ഓർഡറുകൾ', customerAccount: 'ഉപഭോക്തൃ അക്കൗണ്ട്', liveUpdates: 'ലൈവ് അപ്ഡേറ്റുകൾ',
    refresh: 'റിഫ്രഷ്', back: 'പിന്നിലേക്ക്', startShopping: 'ഷോപ്പിംഗ് ആരംഭിക്കുക',
    noOrders: 'ഇതുവരെ ഓർഡറുകളില്ല', orderPlaced: 'ഓർഡർ നൽകി',
    acceptedPreparing: 'സ്വീകരിച്ചു, തയ്യാറാക്കുന്നു', outForDelivery: 'ഡെലിവറിക്ക് പുറപ്പെട്ടു',
    delivered: 'ഡെലിവർ ചെയ്തു', rejected: 'ഓർഡർ നിരസിച്ചു', items: 'ഇനങ്ങൾ',
    qty: 'അളവ്', deliveryAddress: 'ഡെലിവറി വിലാസം', total: 'ആകെ', trackOrder: 'ഓർഡർ ട്രാക്ക് ചെയ്യുക',
    yourCart: 'നിങ്ങളുടെ കാർട്ട്', cartEmpty: 'നിങ്ങളുടെ കാർട്ട് ശൂന്യമാണ്', proceedCheckout: 'ചെക്ക്ഔട്ടിലേക്ക് പോകുക',
    language: 'ഭാഷ',
  },
  mr: {
    orders: 'ऑर्डर्स', profile: 'प्रोफाइल', cart: 'कार्ट', signIn: 'साइन इन',
    welcomeBack: 'पुन्हा स्वागत आहे', createAccount: 'खाते तयार करा', password: 'पासवर्ड',
    email: 'ईमेल', phone: 'मोबाईल नंबर', fullName: 'पूर्ण नाव',
    myOrders: 'माझे ऑर्डर्स', customerAccount: 'ग्राहक खाते', liveUpdates: 'थेट अपडेट्स',
    refresh: 'रिफ्रेश', back: 'मागे', startShopping: 'खरेदी सुरू करा',
    noOrders: 'अजून ऑर्डर्स नाहीत', orderPlaced: 'ऑर्डर दिली',
    acceptedPreparing: 'स्वीकारले आणि तयार होत आहे', outForDelivery: 'डिलिव्हरीसाठी निघाले',
    delivered: 'डिलिव्हर झाले', rejected: 'ऑर्डर नाकारली', items: 'वस्तू',
    qty: 'प्रमाण', deliveryAddress: 'डिलिव्हरी पत्ता', total: 'एकूण', trackOrder: 'ऑर्डर ट्रॅक करा',
    yourCart: 'तुमची कार्ट', cartEmpty: 'तुमची कार्ट रिकामी आहे', proceedCheckout: 'चेकआउटला जा',
    language: 'भाषा',
  },
  gu: {
    orders: 'ઓર્ડર', profile: 'પ્રોફાઇલ', cart: 'કાર્ટ', signIn: 'સાઇન ઇન',
    welcomeBack: 'ફરી સ્વાગત છે', createAccount: 'ખાતું બનાવો', password: 'પાસવર્ડ',
    email: 'ઇમેઇલ', phone: 'મોબાઇલ નંબર', fullName: 'પૂરું નામ',
    myOrders: 'મારા ઓર્ડર', customerAccount: 'ગ્રાહક ખાતું', liveUpdates: 'લાઇવ અપડેટ્સ',
    refresh: 'રિફ્રેશ', back: 'પાછળ', startShopping: 'શોપિંગ શરૂ કરો',
    noOrders: 'હજી કોઈ ઓર્ડર નથી', orderPlaced: 'ઓર્ડર મૂકાયો',
    acceptedPreparing: 'સ્વીકાર્યો અને તૈયાર થઈ રહ્યો છે', outForDelivery: 'ડિલિવરી માટે નીકળ્યો',
    delivered: 'ડિલિવર થયો', rejected: 'ઓર્ડર નામંજૂર', items: 'વસ્તુઓ',
    qty: 'જથ્થો', deliveryAddress: 'ડિલિવરી સરનામું', total: 'કુલ', trackOrder: 'ઓર્ડર ટ્રૅક કરો',
    yourCart: 'તમારી કાર્ટ', cartEmpty: 'તમારી કાર્ટ ખાલી છે', proceedCheckout: 'ચેકઆઉટ પર જાઓ',
    language: 'ભાષા',
  },
  bn: {
    orders: 'অর্ডার', profile: 'প্রোফাইল', cart: 'কার্ট', signIn: 'সাইন ইন',
    welcomeBack: 'আবার স্বাগতম', createAccount: 'অ্যাকাউন্ট তৈরি করুন', password: 'পাসওয়ার্ড',
    email: 'ইমেল', phone: 'মোবাইল নম্বর', fullName: 'পুরো নাম',
    myOrders: 'আমার অর্ডার', customerAccount: 'গ্রাহক অ্যাকাউন্ট', liveUpdates: 'লাইভ আপডেট',
    refresh: 'রিফ্রেশ', back: 'পেছনে', startShopping: 'শপিং শুরু করুন',
    noOrders: 'এখনও কোনো অর্ডার নেই', orderPlaced: 'অর্ডার করা হয়েছে',
    acceptedPreparing: 'গৃহীত এবং প্রস্তুত হচ্ছে', outForDelivery: 'ডেলিভারির জন্য বেরিয়েছে',
    delivered: 'ডেলিভার হয়েছে', rejected: 'অর্ডার বাতিল', items: 'পণ্য',
    qty: 'পরিমাণ', deliveryAddress: 'ডেলিভারি ঠিকানা', total: 'মোট', trackOrder: 'অর্ডার ট্র্যাক করুন',
    yourCart: 'আপনার কার্ট', cartEmpty: 'আপনার কার্ট খালি', proceedCheckout: 'চেকআউটে যান',
    language: 'ভাষা',
  },
  pa: {
    orders: 'ਆਰਡਰ', profile: 'ਪ੍ਰੋਫਾਈਲ', cart: 'ਕਾਰਟ', signIn: 'ਸਾਈਨ ਇਨ',
    welcomeBack: 'ਮੁੜ ਸਵਾਗਤ ਹੈ', createAccount: 'ਖਾਤਾ ਬਣਾਓ', password: 'ਪਾਸਵਰਡ',
    email: 'ਈਮੇਲ', phone: 'ਮੋਬਾਈਲ ਨੰਬਰ', fullName: 'ਪੂਰਾ ਨਾਮ',
    myOrders: 'ਮੇਰੇ ਆਰਡਰ', customerAccount: 'ਗਾਹਕ ਖਾਤਾ', liveUpdates: 'ਲਾਈਵ ਅੱਪਡੇਟ',
    refresh: 'ਰਿਫ੍ਰੈਸ਼', back: 'ਵਾਪਸ', startShopping: 'ਖਰੀਦਦਾਰੀ ਸ਼ੁਰੂ ਕਰੋ',
    noOrders: 'ਹਾਲੇ ਕੋਈ ਆਰਡਰ ਨਹੀਂ', orderPlaced: 'ਆਰਡਰ ਕੀਤਾ ਗਿਆ',
    acceptedPreparing: 'ਸਵੀਕਾਰਿਆ ਅਤੇ ਤਿਆਰ ਹੋ ਰਿਹਾ ਹੈ', outForDelivery: 'ਡਿਲਿਵਰੀ ਲਈ ਨਿਕਲਿਆ',
    delivered: 'ਡਿਲਿਵਰ ਹੋਇਆ', rejected: 'ਆਰਡਰ ਰੱਦ', items: 'ਚੀਜ਼ਾਂ',
    qty: 'ਮਾਤਰਾ', deliveryAddress: 'ਡਿਲਿਵਰੀ ਪਤਾ', total: 'ਕੁੱਲ', trackOrder: 'ਆਰਡਰ ਟ੍ਰੈਕ ਕਰੋ',
    yourCart: 'ਤੁਹਾਡੀ ਕਾਰਟ', cartEmpty: 'ਤੁਹਾਡੀ ਕਾਰਟ ਖਾਲੀ ਹੈ', proceedCheckout: 'ਚੈਕਆਉਟ ਤੇ ਜਾਓ',
    language: 'ਭਾਸ਼ਾ',
  },
} as const;

export const WEB_LANGUAGES: { code: WebLanguage; label: string; native: string }[] = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'ml', label: 'Malayalam', native: 'മലയാളം' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'gu', label: 'Gujarati', native: 'ગુજરાતી' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'pa', label: 'Punjabi', native: 'ਪੰਜਾਬੀ' },
];

type LanguageContextValue = {
  language: WebLanguage;
  setLanguage: (language: WebLanguage) => void;
  t: (key: string) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<WebLanguage>('en');

  useEffect(() => {
    const saved = localStorage.getItem('webLanguage') as WebLanguage | null;
    if (saved && WEB_LANGUAGES.some(item => item.code === saved)) {
      setLanguageState(saved);
    }
  }, []);

  const setLanguage = useCallback((next: WebLanguage) => {
    setLanguageState(next);
    localStorage.setItem('webLanguage', next);
  }, []);

  const value = useMemo(() => ({
    language,
    setLanguage,
    t: (key: TranslationKey) =>
      ((translations as any)[language]?.[key] ?? (translations.en as any)[key] ?? key) as string,
  }), [language, setLanguage]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useWebLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useWebLanguage must be used inside LanguageProvider');
  return context;
}const extraLocales: WebLanguage[] = ['kn', 'ml', 'mr', 'gu', 'bn', 'pa'];


export const WEB_LANGUAGES: { code: WebLanguage; label: string; native: string }[] = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'ml', label: 'Malayalam', native: 'മലയാളം' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'gu', label: 'Gujarati', native: 'ગુજરાતી' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'pa', label: 'Punjabi', native: 'ਪੰਜਾਬੀ' },
];

type LanguageContextValue = {
  language: WebLanguage;
  setLanguage: (language: WebLanguage) => void;
  t: (key: TranslationKey) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<WebLanguage>('en');

  useEffect(() => {
    const saved = localStorage.getItem('webLanguage') as WebLanguage | null;
    if (saved && WEB_LANGUAGES.some(item => item.code === saved)) {
      setLanguageState(saved);
    }
  }, []);

  const setLanguage = useCallback((next: WebLanguage) => {
    setLanguageState(next);
    localStorage.setItem('webLanguage', next);
  }, []);

  const value = useMemo(() => ({
    language,
    setLanguage,
    t: (key: TranslationKey) =>
      ((translations as any)[language]?.[key] ?? (translations.en as any)[key] ?? key) as string,
  }), [language, setLanguage]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useWebLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useWebLanguage must be used inside LanguageProvider');
  return context;
}
