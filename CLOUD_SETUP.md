# Enable private account saving

The account feature is disabled until a dedicated Aaniang Supabase project is configured. The app does not reuse another application's database or credentials.

1. Create a Supabase project at https://supabase.com/dashboard (choose the plan and region yourself).
2. Run `cloud_setup.sql` once in its SQL editor. This creates a notebook table, row-level access policies and a version-checked save function.
3. In Authentication, enable email/password sign-in and create or invite the intended users. Complete the email confirmation/password setup. This app does not create accounts or reset passwords.
4. In Streamlit Community Cloud, open this app's settings and Secrets. Add the following configuration using your project values:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "YOUR-PUBLISHABLE-KEY"
SEC_CONTACT_EMAIL = "YOUR-CONTACT-EMAIL"
```

Use a publishable key (or legacy anon key), **never** a Supabase secret/service-role key. The app refuses elevated keys. Do not put keys, passwords or access tokens in GitHub or chat. SEC_CONTACT_EMAIL is optional and identifies automated SEC requests; users can enter their own contact email in the filing tool.

5. Restart the Streamlit app, expand **Account and cross-device saving**, and sign in. Download any existing session notebook as a backup. Choose **Load cloud notebook** first; a new account begins with an empty cloud notebook. Restore your downloaded notebook if needed, then **Save notebook to my account**. On another device, sign in and load the cloud notebook.

Saving is explicit. If another device saved a newer version, the app rejects the stale save rather than silently overwriting it. Download your local notebook, reload the cloud version and reconcile changes. Signing out clears this session's investment notes and account tokens; it does not delete your cloud notebook.

## Verify access before inviting users

- Sign in as user A, save a notebook, then sign in as user B in a separate browser. B should start with an empty notebook and cannot load or update A's row.
- The anonymous API role must not read or write the table. Both the table and save function must retain the policies and grants in the supplied SQL.
- Load one account on two devices. Save on the first; a save from the stale second device must report a conflict.

The local test suite checks API credential handling, account filtering and conflict handling with simulated responses. These checks do not replace the live two-account database test above, which requires your configured project.

Sources: [Supabase row-level security](https://supabase.com/docs/guides/database/postgres/row-level-security), [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys), [SEC fair access](https://www.sec.gov/about/developer-resources).
