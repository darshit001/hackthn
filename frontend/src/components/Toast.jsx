export function Toast({ text, show }) {
  return <div className={`toast${show ? " show" : ""}`} role="status">{text}</div>;
}
