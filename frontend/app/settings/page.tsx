import Content from "./page-content";
import { requireSignIn } from "../../lib/auth-server";

export const dynamic = "force-dynamic";

export default async function Page() {
  await requireSignIn();
  return <Content />;
}
