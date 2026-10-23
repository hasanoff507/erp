import { RouterProvider } from "react-router-dom";

import { Toaster } from "@shared/ui";

import { AuthProvider } from "#/features/auth-provider/index.ts";

import { createAppRouter, LOGIN_SUBSCRIPTION_EXPIRED } from "./router/index.tsx";

const router = createAppRouter();

/** 403 SUBSCRIPTION_RESTRICTED → /login?reason=subscription_expired — not a logout (14 §16.1.4). */
const goToSubscriptionLogin = () => {
  void router.navigate(LOGIN_SUBSCRIPTION_EXPIRED, { replace: true });
};

export function App() {
  return (
    <AuthProvider onSubscriptionRestricted={goToSubscriptionLogin}>
      <RouterProvider router={router} />
      <Toaster />
    </AuthProvider>
  );
}
