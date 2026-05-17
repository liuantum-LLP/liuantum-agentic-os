type LoadingSpinnerProps = {
  label?: string;
};

export function LoadingSpinner({ label = "Loading local data" }: LoadingSpinnerProps) {
  return (
    <div className="state-box loading-state">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
