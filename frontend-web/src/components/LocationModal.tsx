'use client';

import { useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  MapPin, LocateFixed, X, Search, Check, Loader2, Sparkles, ArrowRight, ShieldCheck,
} from 'lucide-react';
import styles from './LocationModal.module.css';

interface LocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectLocation?: (city: string, pincode: string, address?: string) => void;
  onLocationSelected?: (area: string) => void;
}

const POPULAR_CITIES = [
  { name: 'Bengaluru', pincode: '560001' },
  { name: 'Mumbai', pincode: '400001' },
  { name: 'New Delhi', pincode: '110001' },
  { name: 'Hyderabad', pincode: '500001' },
  { name: 'Chennai', pincode: '600001' },
  { name: 'Kolkata', pincode: '700001' },
  { name: 'Pune', pincode: '411001' },
  { name: 'Ahmedabad', pincode: '380001' },
];

export default function LocationModal({ isOpen, onClose, onSelectLocation, onLocationSelected }: LocationModalProps) {
  const shouldReduceMotion = Boolean(useReducedMotion());
  const [detecting, setDetecting] = useState(false);
  const [pincode, setPincode] = useState('');
  const [loadingPincode, setLoadingPincode] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const saveAndClose = (city: string, pin: string, formatted?: string) => {
    const areaLabel = [city, pin].filter(Boolean).join(' ');
    localStorage.setItem('retailMindArea', areaLabel);
    if (city) localStorage.setItem('retailMindCity', city);
    if (pin) localStorage.setItem('retailMindPincode', pin);
    if (formatted) localStorage.setItem('retailMindAddress', formatted);

    window.dispatchEvent(new Event('retailmind:area'));
    onSelectLocation?.(city, pin, formatted);
    onLocationSelected?.(areaLabel);

    setSuccess(`Delivering to ${city}${pin ? ` (${pin})` : ''}`);
    setTimeout(() => {
      setSuccess('');
      onClose();
    }, 600);
  };

  const handleDetectGPS = () => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser.');
      return;
    }

    setDetecting(true);
    setError('');
    setSuccess('');

    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const res = await fetch(
            `/api/location?lat=${coords.latitude}&lon=${coords.longitude}`,
            { cache: 'no-store' },
          );
          const data = await res.json();

          if (!res.ok || !data.success) {
            throw new Error(data.message || 'Unable to decode coordinates.');
          }

          saveAndClose(data.city, data.pincode, data.formattedAddress);
        } catch {
          setError('Could not get precise address. Try entering your pincode below.');
        } finally {
          setDetecting(false);
        }
      },
      (err) => {
        setDetecting(false);
        if (err.code === 1) {
          setError('Location permission denied. Please enter your pincode or allow permission in browser settings.');
        } else {
          setError('Location request timed out. Please enter your pincode.');
        }
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 },
    );
  };

  const handleApplyPincode = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanPin = pincode.trim();

    if (!/^\d{6}$/.test(cleanPin)) {
      setError('Please enter a valid 6-digit Indian PIN code.');
      return;
    }

    setLoadingPincode(true);
    setError('');
    setSuccess('');

    try {
      const res = await fetch(`/api/location?pincode=${cleanPin}`, { cache: 'no-store' });
      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.message || 'Pincode not found.');
      }

      saveAndClose(data.city, cleanPin, data.formattedAddress);
    } catch {
      setError('Could not verify this pincode. Please try again.');
    } finally {
      setLoadingPincode(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className={styles.backdrop} onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="location-modal-title">
          <motion.div
            className={styles.modal}
            onClick={(e) => e.stopPropagation()}
            initial={shouldReduceMotion ? false : { opacity: 0, scale: 0.94, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={shouldReduceMotion ? undefined : { opacity: 0, scale: 0.95, y: 12 }}
            transition={{ duration: 0.24, ease: [0.2, 0.8, 0.2, 1] }}
          >
            {/* Header */}
            <div className={styles.header}>
              <div className={styles.headerTitle}>
                <div className={styles.mapPinOrb}>
                  <MapPin size={20} />
                </div>
                <div>
                  <h3 id="location-modal-title">Select Delivery Location</h3>
                  <p>Check store availability, live stock & fast delivery</p>
                </div>
              </div>
              <button className={styles.closeButton} onClick={onClose} aria-label="Close location dialog">
                <X size={18} />
              </button>
            </div>

            {/* GPS Auto-Detect Button (Flipkart Style) */}
            <div className={styles.body}>
              <button
                type="button"
                className={styles.detectButton}
                onClick={handleDetectGPS}
                disabled={detecting}
              >
                <div className={styles.detectIconWrap}>
                  {detecting ? (
                    <Loader2 size={20} className={styles.spin} />
                  ) : (
                    <LocateFixed size={20} />
                  )}
                  {detecting && <span className={styles.radarWave} />}
                </div>
                <div className={styles.detectCopy}>
                  <strong>{detecting ? 'Detecting precise coordinates…' : 'Use my current location'}</strong>
                  <span>{detecting ? 'Accessing high-accuracy GPS sync' : 'Using GPS for instant neighbourhood detection'}</span>
                </div>
                <ArrowRight size={16} className={styles.detectArrow} />
              </button>

              <div className={styles.divider}>
                <span>OR ENTER PINCODE</span>
              </div>

              {/* Pincode Input Form */}
              <form onSubmit={handleApplyPincode} className={styles.pincodeForm}>
                <div className={styles.inputWrap}>
                  <Search size={17} className={styles.inputIcon} />
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    value={pincode}
                    onChange={(e) => setPincode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="Enter 6-digit delivery pincode (e.g. 560001)"
                    aria-label="Enter 6-digit pincode"
                  />
                  {pincode.length > 0 && (
                    <button type="button" className={styles.clearInput} onClick={() => setPincode('')}>
                      <X size={14} />
                    </button>
                  )}
                </div>
                <button
                  type="submit"
                  className={styles.applyButton}
                  disabled={pincode.length !== 6 || loadingPincode}
                >
                  {loadingPincode ? <Loader2 size={16} className={styles.spin} /> : 'Apply'}
                </button>
              </form>

              {/* Status alerts */}
              {error && (
                <div className={styles.errorAlert} role="alert">
                  {error}
                </div>
              )}
              {success && (
                <div className={styles.successAlert} role="status">
                  <Check size={16} /> {success}
                </div>
              )}

              {/* Popular Cities */}
              <div className={styles.popularSection}>
                <span className={styles.popularTitle}>POPULAR CITIES</span>
                <div className={styles.popularGrid}>
                  {POPULAR_CITIES.map((city) => (
                    <button
                      key={city.name}
                      type="button"
                      className={styles.cityChip}
                      onClick={() => saveAndClose(city.name, city.pincode)}
                    >
                      <MapPin size={12} />
                      <span>{city.name}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className={styles.footerNote}>
                <ShieldCheck size={13} />
                <span>Shows verified catalogues and local inventory from shops near you.</span>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
