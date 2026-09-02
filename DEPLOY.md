# Put AANIANG Trading Station online

This lets the app work on an iPhone even when the computer is off.

## What you need

Create free accounts at GitHub and Streamlit Community Cloud. You do not need to install anything or run commands on your iPhone.

## Publish the app

1. Go to https://github.com and create a free account, if you do not already have one.
2. Create a new repository called `aaniang-trading-station`. Leave the options at their default values and create it.
3. In the new repository, select **Add file**, then **Upload files**.
4. Upload `app.py`, every `.py` file, the `tests` folder, `requirements.txt`, `README.md`, `DEPLOY.md`, and `senegal_flag.svg`. Do not upload `user_data`.
5. Go to https://share.streamlit.io and select **Continue with GitHub**.
6. Select your `aaniang-trading-station` repository, choose branch `main`, and set the main file path to `app.py`.
7. Select **Deploy**. Streamlit will show a public web address after it finishes.

## Use it on iPhone

1. Open the public web address in Safari.
2. Tap the Share button.
3. Choose **Add to Home Screen** and tap **Add**.

The AANIANG Trading Station icon will appear on your iPhone Home Screen. Opening it uses the hosted app, so your computer can remain off.

## Important

Streamlit's free tier is suitable for a personal trial and can sleep after inactivity. The first visit after it sleeps may take a moment. For reliable broad-market scanning, choose a paid Streamlit plan or another always-on Python hosting service later.
