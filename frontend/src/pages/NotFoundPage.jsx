import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui";

export default function NotFoundPage() {
  return (
    <div className="page">
      <EmptyState title="Page not found">
        <Link className="button primary" to="/students">
          Go to students
        </Link>
      </EmptyState>
    </div>
  );
}
