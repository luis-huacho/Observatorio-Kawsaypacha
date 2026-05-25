import { useEffect, useState } from "react";

type State<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "ok"; data: T; error: null }
  | { status: "error"; data: null; error: Error };

const cache = new Map<string, unknown>();

export function useJsonData<T>(url: string): State<T> {
  const [state, setState] = useState<State<T>>(() => {
    if (cache.has(url)) {
      return { status: "ok", data: cache.get(url) as T, error: null };
    }
    return { status: "loading", data: null, error: null };
  });

  useEffect(() => {
    let active = true;
    if (cache.has(url)) {
      setState({ status: "ok", data: cache.get(url) as T, error: null });
      return;
    }
    setState({ status: "loading", data: null, error: null });
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.json();
      })
      .then((data: T) => {
        if (!active) return;
        cache.set(url, data);
        setState({ status: "ok", data, error: null });
      })
      .catch((err: Error) => {
        if (!active) return;
        setState({ status: "error", data: null, error: err });
      });
    return () => {
      active = false;
    };
  }, [url]);

  return state;
}
