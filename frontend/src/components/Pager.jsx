import { Fragment } from "react";
import { PER_PAGE } from "../lib/constants";
import { Icon } from "./Icon";

// 1 … 4 5 6 … 12: first, last and the neighbours of the current page
export function Pager({ page, pages, total, onPage }) {
  if (pages < 2) return null;
  const from = (page - 1) * PER_PAGE;
  const nums = [...new Set([1, page - 1, page, page + 1, pages])].filter(n => n >= 1 && n <= pages).sort((a, b) => a - b);
  return (
    <div className="pager">
      <span>Showing {from + 1}–{Math.min(from + PER_PAGE, total)} of {total}</span>
      <nav aria-label="Video pages">
        <button type="button" className="btn icon" aria-label="Previous page" disabled={page === 1} onClick={() => onPage(page - 1)}><Icon name="left" /></button>
        {nums.map((n, i) => (
          <Fragment key={n}>
            {i > 0 && n - nums[i - 1] > 1 && <span className="gap" aria-hidden="true">…</span>}
            <button type="button" className="btn" aria-label={`Page ${n}`} aria-current={n === page ? "page" : undefined} onClick={() => onPage(n)}>{n}</button>
          </Fragment>
        ))}
        <button type="button" className="btn icon" aria-label="Next page" disabled={page === pages} onClick={() => onPage(page + 1)}><Icon name="right" /></button>
      </nav>
    </div>
  );
}
