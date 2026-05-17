type ErrorDisplayProps = {
  message: string;
};

export function ErrorDisplay({ message }: ErrorDisplayProps) {
  return (
    <div className="state-box error-state">
      <strong>Something needs attention.</strong>
      <span>{message}</span>
    </div>
  );
}
