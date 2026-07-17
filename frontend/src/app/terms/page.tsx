import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Terms of Service - Kafi Social Media Agent',
  description:
    'Terms of Service governing the use of the Kafi Commodities Social Media Agent application.',
};

const LAST_UPDATED = 'July 17, 2026';
const COMPANY = 'Kafi Commodities';
const APP_NAME = 'Kafi Social Media Agent';
const CONTACT_EMAIL = 'support@kaficommodities.com';

export default function TermsOfServicePage() {
  return (
    <main className="min-h-screen bg-white text-slate-800">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-3xl font-bold text-slate-900">Terms of Service</h1>
        <p className="mt-2 text-sm text-slate-500">Last updated: {LAST_UPDATED}</p>

        <section className="mt-8 space-y-4 leading-relaxed">
          <p>
            These Terms of Service (&ldquo;Terms&rdquo;) govern your access to and use of the{' '}
            {APP_NAME} (the &ldquo;Service&rdquo;) operated by {COMPANY} (&ldquo;we&rdquo;,
            &ldquo;us&rdquo;, or &ldquo;our&rdquo;). By accessing or using the Service, you agree to
            be bound by these Terms.
          </p>
        </section>

        <Section title="1. Use of the Service">
          <p>
            The Service allows authorized users to create, schedule, publish, and analyze social
            media content across connected platforms such as Facebook, Instagram, YouTube, and
            LinkedIn. You agree to use the Service only for lawful purposes and in compliance with
            all applicable platform policies.
          </p>
        </Section>

        <Section title="2. Account Connections and Authorization">
          <p>
            To use publishing and analytics features, you must connect social media accounts via
            official OAuth authorization. You represent that you are authorized to manage any account
            you connect. You may revoke access at any time through the Service or the relevant
            platform&rsquo;s settings.
          </p>
        </Section>

        <Section title="3. Third-Party Platforms">
          <p>
            The Service integrates with third-party platforms and their APIs. Your use of those
            platforms is subject to their respective terms, including the Meta Platform Terms, the{' '}
            <a
              className="text-brand-700 underline"
              href="https://www.youtube.com/t/terms"
              target="_blank"
              rel="noopener noreferrer"
            >
              YouTube Terms of Service
            </a>
            , and the LinkedIn User Agreement. We are not responsible for the availability, policies,
            or actions of these third-party platforms.
          </p>
        </Section>

        <Section title="4. Content Responsibility">
          <p>
            You are solely responsible for the content you create, upload, schedule, or publish
            through the Service. You must own or have the necessary rights to all such content and
            ensure it does not violate any law or third-party rights.
          </p>
        </Section>

        <Section title="5. Acceptable Use">
          <ul className="mt-3 list-disc space-y-2 pl-6">
            <li>Do not use the Service to publish unlawful, misleading, or infringing content.</li>
            <li>Do not attempt to disrupt, reverse engineer, or gain unauthorized access to the Service.</li>
            <li>Do not use the Service to violate any social platform&rsquo;s terms or policies.</li>
          </ul>
        </Section>

        <Section title="6. Intellectual Property">
          <p>
            The Service, including its software and design, is owned by {COMPANY} and protected by
            applicable intellectual property laws. These Terms do not grant you any rights to our
            trademarks or branding.
          </p>
        </Section>

        <Section title="7. Disclaimer of Warranties">
          <p>
            The Service is provided &ldquo;as is&rdquo; and &ldquo;as available&rdquo; without
            warranties of any kind, whether express or implied. We do not warrant that the Service
            will be uninterrupted, error-free, or secure.
          </p>
        </Section>

        <Section title="8. Limitation of Liability">
          <p>
            To the maximum extent permitted by law, {COMPANY} shall not be liable for any indirect,
            incidental, or consequential damages arising from your use of the Service.
          </p>
        </Section>

        <Section title="9. Termination">
          <p>
            We may suspend or terminate access to the Service at any time for conduct that violates
            these Terms or applicable platform policies.
          </p>
        </Section>

        <Section title="10. Changes to These Terms">
          <p>
            We may update these Terms from time to time. Continued use of the Service after changes
            become effective constitutes acceptance of the updated Terms.
          </p>
        </Section>

        <Section title="11. Contact Us">
          <p>
            For questions about these Terms, contact us at{' '}
            <a className="text-brand-700 underline" href={`mailto:${CONTACT_EMAIL}`}>
              {CONTACT_EMAIL}
            </a>
            .
          </p>
        </Section>

        <p className="mt-12 text-sm text-slate-500">
          &copy; {new Date().getFullYear()} {COMPANY}. All rights reserved.
        </p>
      </div>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
      <div className="mt-2 leading-relaxed text-slate-700">{children}</div>
    </section>
  );
}
