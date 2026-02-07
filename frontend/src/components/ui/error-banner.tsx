/** Error banner with message and optional retry. */

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div className="m-6 p-4 bg-red-900/30 border border-red-800 rounded-lg flex items-center justify-between">
      <p className="text-red-300 text-sm">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="ml-4 px-3 py-1 text-xs font-medium bg-red-800 hover:bg-red-700 rounded transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
