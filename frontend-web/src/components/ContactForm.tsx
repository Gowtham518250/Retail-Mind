'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AlertCircle, CheckCircle2, Loader2, Send } from 'lucide-react';
import styles from './ContactForm.module.css';

interface FormState {
  name: string;
  email: string;
  subject: string;
  message: string;
}

type FieldErrors = Partial<Record<keyof FormState, string>>;

const initialForm: FormState = {
  name: '',
  email: '',
  subject: '',
  message: '',
};

const subjects = [
  'Order support',
  'Shop or product question',
  'Accessibility feedback',
  'Privacy request',
  'Something else',
];

export default function ContactForm({ supportEmail }: { supportEmail: string }) {
  const [form, setForm] = useState<FormState>(initialForm);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [status, setStatus] = useState<'idle' | 'opening' | 'opened'>('idle');
  const [submitError, setSubmitError] = useState('');

  const setField = (key: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
    setSubmitError('');
    setStatus('idle');
  };

  const validate = (): FieldErrors => {
    const next: FieldErrors = {};
    if (form.name.trim().length < 2) next.name = 'Enter your name (at least 2 characters).';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      next.email = 'Enter a valid email address so we can reply.';
    }
    if (!form.subject) next.subject = 'Choose a subject.';
    if (form.message.trim().length < 20) {
      next.message = 'Add a little more detail (at least 20 characters).';
    } else if (form.message.trim().length > 2000) {
      next.message = 'Keep your message under 2,000 characters.';
    }
    return next;
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (status === 'opening') return;

    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      const firstField = (Object.keys(nextErrors)[0] || '') as keyof FormState;
      document.getElementById(`contact-${firstField}`)?.focus();
      return;
    }

    if (!supportEmail) {
      setSubmitError('A verified support email address is not configured for this website yet.');
      return;
    }

    const subject = `[Retail Mind] ${form.subject}`;
    const body = [
      `Name: ${form.name.trim()}`,
      `Reply email: ${form.email.trim()}`,
      `Subject: ${form.subject}`,
      '',
      form.message.trim(),
    ].join('\n');

    setStatus('opening');
    setSubmitError('');
    window.location.href = `mailto:${supportEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

    window.setTimeout(() => {
      setStatus('opened');
    }, 400);
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <div className={styles.row}>
        <div className={styles.field}>
          <label htmlFor="contact-name">Your name</label>
          <input
            id="contact-name"
            name="name"
            type="text"
            autoComplete="name"
            value={form.name}
            onChange={(event) => setField('name', event.target.value)}
            placeholder="Your name"
            aria-invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? 'contact-name-error' : undefined}
            required
          />
          {errors.name && <span id="contact-name-error" className={styles.error}><AlertCircle size={14} /> {errors.name}</span>}
        </div>

        <div className={styles.field}>
          <label htmlFor="contact-email">Email address</label>
          <input
            id="contact-email"
            name="email"
            type="email"
            autoComplete="email"
            value={form.email}
            onChange={(event) => setField('email', event.target.value)}
            placeholder="you@example.com"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'contact-email-error' : undefined}
            required
          />
          {errors.email && <span id="contact-email-error" className={styles.error}><AlertCircle size={14} /> {errors.email}</span>}
        </div>
      </div>

      <div className={styles.field}>
        <label htmlFor="contact-subject">Subject</label>
        <select
          id="contact-subject"
          name="subject"
          value={form.subject}
          onChange={(event) => setField('subject', event.target.value)}
          aria-invalid={Boolean(errors.subject)}
          aria-describedby={errors.subject ? 'contact-subject-error' : undefined}
          required
        >
          <option value="">Choose a subject</option>
          {subjects.map((subject) => <option key={subject} value={subject}>{subject}</option>)}
        </select>
        {errors.subject && <span id="contact-subject-error" className={styles.error}><AlertCircle size={14} /> {errors.subject}</span>}
      </div>

      <div className={styles.field}>
        <div className={styles.labelRow}>
          <label htmlFor="contact-message">Message</label>
          <span>{form.message.length}/2000</span>
        </div>
        <textarea
          id="contact-message"
          name="message"
          rows={7}
          value={form.message}
          onChange={(event) => setField('message', event.target.value)}
          placeholder="Tell us what you need help with. Do not include passwords, one-time codes, or full card details."
          maxLength={2000}
          aria-invalid={Boolean(errors.message)}
          aria-describedby={errors.message ? 'contact-message-error' : 'contact-message-help'}
          required
        />
        <span id="contact-message-help" className={styles.help}>
          We use your name and email only to reply to this message. Read our{' '}
          <Link href="/privacy">privacy information</Link>.
        </span>
        {errors.message && <span id="contact-message-error" className={styles.error}><AlertCircle size={14} /> {errors.message}</span>}
      </div>

      {submitError && (
        <div className={styles.noticeError} role="alert">
          <AlertCircle size={16} /> {submitError}
        </div>
      )}

      {status === 'opened' && (
        <div className={styles.notice} role="status">
          <CheckCircle2 size={16} />
          <span>
            Your email app should now be open with this message. It has <strong>not</strong> been sent to
            Retail Mind until you choose Send in that app.
          </span>
        </div>
      )}

      <button type="submit" className={styles.submit} disabled={status === 'opening'}>
        {status === 'opening'
          ? <><Loader2 size={17} className="spin" /> Opening your email app…</>
          : <><Send size={17} /> Open email draft</>}
      </button>
      <p className={styles.smallPrint}>
        This website does not currently store contact-form submissions itself. The prepared email is sent
        through your own email provider only after you confirm it there.
      </p>
    </form>
  );
}
