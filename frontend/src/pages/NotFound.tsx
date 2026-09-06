import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="grid min-h-dvh place-items-center bg-bg p-6">
      <div className="max-w-md space-y-4 text-center">
        <p className="text-stat font-bold text-primary">404</p>
        <h1 className="text-h1 font-bold text-ink">{t('common.not_found_title')}</h1>
        <Link
          to="/"
          className="inline-flex min-h-tap-primary items-center rounded-md bg-primary px-5 font-semibold text-primary-on"
        >
          {t('common.go_home')}
        </Link>
      </div>
    </div>
  );
}
