import { runtimeApi } from "../../api/runtimeApi";
import { useAsync } from "../../hooks/useAsync";
import { ProviderHealthPanel } from "../../components/ProviderCards";

export function ProvidersPage() {
  const statuses = useAsync(() => runtimeApi.providerStatuses(false), []);
  async function refresh() {
    await runtimeApi.providerStatuses(true);
    await statuses.reload();
  }
  const providers = statuses.value?.providers || {};
  return <ProviderHealthPanel providers={providers} onRefresh={refresh} />;
}
