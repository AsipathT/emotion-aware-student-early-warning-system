import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

// Allowed input values, descriptions and model info from GET /api/reference.
const ReferenceContext = createContext(null);

export function ReferenceProvider({ children }) {
  const [reference, setReference] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/reference")
      .then(setReference)
      .catch((err) => setError(err.message));
  }, []);

  return <ReferenceContext.Provider value={{ reference, error }}>{children}</ReferenceContext.Provider>;
}

export const useReference = () => useContext(ReferenceContext);

export function riskTierFor(probability, reference) {
  const bounds = reference?.risk_tier_bounds || [];
  const match = bounds.find((b) => probability <= b.upper);
  return match ? match.tier : bounds.at(-1)?.tier;
}
