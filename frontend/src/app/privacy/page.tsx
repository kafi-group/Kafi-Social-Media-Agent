import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Privacy Policy - Kafi Social Media Agent',
  description:
    'Privacy Policy for the Kafi Commodities Social Media Agent, describing how data from connected social platforms is collected, used, and protected.',
};

const LAST_UPDATED = 'July 17, 2026';
const COMPANY = 'Kafi Commodities';
const APP_NAME = 'Kafi Social Media Agent';
const CONTACT_EMAIL = 'privacy@kaficommodities.com';

export default function PrivacyPolicyPage() {
  return (
    <main className="min-h-screen bg-white text-slate-800">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-3xl font-bold text-slate-900">Privacy Policy</h1>
        <p className="mt-2 text-sm text-slate-500">Last updated: {LAST_UPDATED}</p>

        <section className="mt-8 space-y-4 leading-relaxed">
          <p>
            This Privacy Policy explains how {COMPANY} (&ldquo;we&rdquo;, &ldquo;us&rdquo;, or
            &ldquo;our&rdquo;) collects, uses, and protects information in connection with the{' '}
            {APP_NAME} (the &ldquo;Service&rdquo;). The Service is an internal tool used to create,
            schedule, publish, and analyze content across social media platforms including Facebook,
            Instagram, YouTube, and LinkedIn.
          </p>
        </section>

        <Section title="1. Information We Collect">
          <p>We collect and process the following categories of information:</p>
          <ul className="mt-3 list-disc space-y-2 pl-6">
            <li>
              <strong>Account authorization data:</strong> access tokens and account identifiers
              provided by social platforms (e.g. Facebook Pages, Instagram Business accounts, YouTube
              channels, LinkedIn profiles) when you connect them via official OAuth flows.
            </li>
            <li>
              <strong>Content you create:</strong> captions, images, videos, and scheduling
              information you generate or upload for publishing.
            </li>
            <li>
              <strong>Analytics and insights:</strong> aggregated performance metrics (views, reach,
              engagement, followers) retrieved from the connected platforms&rsquo; official APIs.
            </li>
            <li>
              <strong>Publicly available competitor data:</strong> public metrics from competitor
              accounts you choose to track, obtained through the platforms&rsquo; official public
              APIs.
            </li>
          </ul>
        </Section>

        <Section title="2. How We Use Information">
          <ul className="mt-3 list-disc space-y-2 pl-6">
            <li>To publish and schedule content to the social accounts you have connected.</li>
            <li>To display analytics and engagement insights for those accounts.</li>
            <li>To generate content suggestions and competitive analysis.</li>
            <li>To maintain valid API connections by refreshing authorization tokens.</li>
          </ul>
          <p className="mt-3">
            We do not sell your personal data, and we do not use it for advertising.
          </p>
        </Section>

        <Section title="3. Data From Meta Platforms (Facebook &amp; Instagram)">
          <p>
            When you connect a Facebook Page or Instagram Business account, we access only the
            permissions you approve, which may include reading Page and Instagram insights, reading
            content, and publishing content on your behalf. This data is used solely to provide the
            Service&rsquo;s publishing and analytics features and is handled in accordance with the
            Meta Platform Terms and Developer Policies.
          </p>
        </Section>

        <Section title="4. Data From Google / YouTube">
          <p>
            The Service&rsquo;s use of information received from Google APIs adheres to the{' '}
            <a
              className="text-brand-700 underline"
              href="https://developers.google.com/terms/api-services-user-data-policy"
              target="_blank"
              rel="noopener noreferrer"
            >
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements. YouTube features rely on YouTube API Services
            and are subject to the{' '}
            <a
              className="text-brand-700 underline"
              href="https://www.youtube.com/t/terms"
              target="_blank"
              rel="noopener noreferrer"
            >
              YouTube Terms of Service
            </a>{' '}
            and the{' '}
            <a
              className="text-brand-700 underline"
              href="https://policies.google.com/privacy"
              target="_blank"
              rel="noopener noreferrer"
            >
              Google Privacy Policy
            </a>
            .
          </p>
        </Section>

        <Section title="5. Data Storage and Security">
          <p>
            Authorization tokens and content are stored securely and used only to operate the
            Service. We apply reasonable administrative and technical safeguards to protect this
            information. Access is limited to authorized operators of {COMPANY}.
          </p>
        </Section>

        <Section title="6. Data Retention and Deletion">
          <p>
            We retain data only as long as needed to provide the Service. You may disconnect any
            connected account at any time, which revokes our access. To request deletion of stored
            data associated with your accounts, contact us at{' '}
            <a className="text-brand-700 underline" href={`mailto:${CONTACT_EMAIL}`}>
              {CONTACT_EMAIL}
            </a>
            . You may also revoke access directly from each platform&rsquo;s settings
            (Facebook/Instagram: Business Integrations; Google: Third-party access).
          </p>
        </Section>

        <Section title="7. Sharing of Information">
          <p>
            We do not share your data with third parties except as required to operate the Service
            (for example, the social platforms&rsquo; own APIs) or as required by law.
          </p>
        </Section>

        <Section title="8. Changes to This Policy">
          <p>
            We may update this Privacy Policy from time to time. Material changes will be reflected
            by updating the &ldquo;Last updated&rdquo; date above.
          </p>
        </Section>

        <Section title="9. Contact Us">
          <p>
            For any questions about this Privacy Policy or your data, contact us at{' '}
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
