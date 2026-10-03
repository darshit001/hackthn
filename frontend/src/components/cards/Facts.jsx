import { Icon } from "../Icon";
import { ICON } from "../../lib/constants";

// community (with its icon), language and length (a ready video shows its real one on the thumbnail), plus any extra facts a card wants to add
export function Facts({ job, label, length = true, children }) {
  return (
    <ul className="facts">
      {job.kind === "image" && <li><Icon name="image" />Image</li>}
      <li><Icon name={ICON[job.community] || "folder"} />{label(job.community)}</li>
      <li>{label(job.language)}</li>
      {length && job.duration != null && <li><Icon name="clock" />{job.duration} s</li>}
      {children}
    </ul>
  );
}
