// /connectors/:id opens the right step for the connector's status.
import { useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { api, type ConnectorDetail } from "../api";

export default function ConnectorRouter() {
  const { id } = useParams();
  const [target, setTarget] = useState<string | null>(null);
  useEffect(() => {
    api.get<ConnectorDetail>(`/api/connectors/${id}`).then((c) => {
      if (c.status.startsWith("live") || c.status === "paused") setTarget("detail");
      else if (c.last_run?.exit_code === 0) setTarget("savings");
      else if (c.status === "testing" || c.from_library) setTarget("connect");
      else if (c.summary) setTarget("found");
      else setTarget("build");
    });
  }, [id]);
  return target ? <Navigate replace to={`/connectors/${id}/${target}`} /> : null;
}
