#!/usr/bin/env python3
"""Klien X (Twitter) berbasis cookie sesi + generator x-client-transaction-id.

Kredensial dibaca dari file di luar folder proyek (lihat AUTH_PATH) dan tidak
pernah ditulis ke dataset mana pun.
"""
import json, os, random, time, urllib.parse
import bs4, requests
from x_client_transaction import ClientTransaction
from x_client_transaction.utils import generate_headers, handle_x_migration, get_ondemand_file_url

# Kredensial sengaja disimpan DI LUAR folder proyek agar tidak pernah ikut
# ter-commit atau tersalin bersama dataset.
AUTH_PATH = os.environ.get("X_AUTH_PATH") or os.path.expanduser(
    "~/.config/virgo-sentiment/x_auth.json")

BEARER = ("AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
          "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# queryId per operasi. Nilai ini berubah tiap rilis X, jadi utamakan hasil
# penambangan bundle (scripts/x_qid.py); daftar di bawah hanya cadangan.
QID = {
    "SearchTimeline": "uGB-gNd5HE4TkpO70OcFNw",
    "TweetDetail": "blErEeZkos5TDrWmrCp7cw",
    "UserByScreenName": "KybxDj9RrADIITXlGG8kpw",
    "UserTweets": "qJy3MbaNndtzxf9IqUzxMg",
    "UserTweetsAndReplies": "Z1m9j8S1leAzQp6yZXuaSg",
}
_QID_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "_bersama", "x_query_ids.json")
if os.path.exists(_QID_FILE):
    try:
        QID.update(json.load(open(_QID_FILE, encoding="utf-8")))
    except Exception:
        pass

FEATURES = {
    "rweb_video_screen_enabled": False, "payments_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "rweb_tipjar_consumption_enabled": True, "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": True,
    "responsive_web_jetfuel_frame": True, "responsive_web_grok_share_attachment_enabled": True,
    "articles_preview_enabled": True, "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True, "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "responsive_web_grok_show_grok_translated_post": False,
    "responsive_web_grok_analysis_button_from_backend": True,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True, "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_grok_image_annotation_enabled": True,
    "responsive_web_grok_community_note_auto_translation_is_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}


class XClient:
    def __init__(self, auth_path=AUTH_PATH, lang="id"):
        a = json.load(open(auth_path, encoding="utf-8"))
        self.ct0, self.auth_token = a["ct0"], a["auth_token"]
        self.lang = lang
        self.s = requests.Session()
        self.s.headers = generate_headers()
        # halaman home HARUS diambil dengan cookie login; versi anonim hanya shell
        # kosong tanpa manifest ondemand.s yang dibutuhkan generator transaction-id.
        self.s.headers["cookie"] = f"auth_token={self.auth_token}; ct0={self.ct0}"
        r = self.s.get("https://x.com/home", timeout=45)
        home = bs4.BeautifulSoup(r.content, "html.parser")
        ond_url = get_ondemand_file_url(response=home)
        ond = self.s.get(ond_url, timeout=45)
        self.ct = ClientTransaction(home, bs4.BeautifulSoup(ond.content, "html.parser"))
        self.api = requests.Session()
        self.api.headers.update({
            "authorization": "Bearer " + BEARER,
            "x-csrf-token": self.ct0,
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": lang,
            "content-type": "application/json",
            "user-agent": UA,
            "referer": "https://x.com/",
            "origin": "https://x.com",
            "accept": "*/*",
            "accept-language": "id-ID,id;q=0.9,en;q=0.8",
            "cookie": f"auth_token={self.auth_token}; ct0={self.ct0}",
        })

    def gql(self, op, variables, features=None, field_toggles=None, retries=3):
        path = f"/i/api/graphql/{QID[op]}/{op}"
        params = {"variables": json.dumps(variables, separators=(",", ":"))}
        params["features"] = json.dumps(features or FEATURES, separators=(",", ":"))
        if field_toggles:
            params["fieldToggles"] = json.dumps(field_toggles, separators=(",", ":"))
        url = "https://x.com" + path + "?" + urllib.parse.urlencode(params)
        last = None
        for i in range(retries):
            tid = self.ct.generate_transaction_id(method="GET", path=path)
            r = self.api.get(url, headers={"x-client-transaction-id": tid}, timeout=45)
            if r.status_code == 200:
                return r.json()
            last = (r.status_code, r.text[:200])
            if r.status_code == 429:               # rate limit -> tunggu lebih lama
                reset = r.headers.get("x-rate-limit-reset")
                wait = 60
                if reset:
                    try: wait = max(10, int(reset) - int(time.time()) + 5)
                    except Exception: pass
                time.sleep(min(wait, 900))
            else:
                time.sleep(3 + i * 4)
        raise RuntimeError(f"gql {op} gagal: {last}")

    def tweet_detail(self, tweet_id, cursor=None):
        """Ambil satu thread lengkap: tweet fokus + balasan (reply)."""
        v = {"focalTweetId": str(tweet_id), "with_rux_injections": False,
             "rankingMode": "Relevance", "includePromotedContent": False,
             "withCommunity": True, "withQuickPromoteEligibilityTweetFields": True,
             "withBirdwatchNotes": True, "withVoice": True}
        if cursor:
            v["cursor"] = cursor
            v["referrer"] = "tweet"
        toggles = {"withArticleRichContentState": True, "withArticlePlainText": False,
                   "withGrokAnalyze": False, "withDisallowedReplyControls": False}
        return self.gql("TweetDetail", v, field_toggles=toggles)

    def user_by_name(self, screen_name):
        v = {"screen_name": screen_name}
        feats = {"responsive_web_grok_bio_auto_translation_is_enabled": False,
                 "hidden_profile_subscriptions_enabled": True,
                 "payments_enabled": False,
                 "profile_label_improvements_pcf_label_in_post_enabled": True,
                 "rweb_tipjar_consumption_enabled": True,
                 "verified_phone_label_enabled": False,
                 "subscriptions_verification_info_is_identity_verified_enabled": True,
                 "subscriptions_verification_info_verified_since_enabled": True,
                 "highlights_tweets_tab_ui_enabled": True,
                 "responsive_web_twitter_article_notes_tab_enabled": True,
                 "subscriptions_feature_can_gift_premium": True,
                 "creator_subscriptions_tweet_preview_api_enabled": True,
                 "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                 "responsive_web_graphql_timeline_navigation_enabled": True}
        return self.gql("UserByScreenName", v, features=feats,
                        field_toggles={"withAuxiliaryUserLabels": True})

    def search(self, raw_query, product="Latest", cursor=None, count=20):
        v = {"rawQuery": raw_query, "count": count, "querySource": "typed_query",
             "product": product, "withGrokTranslatedBio": False,
             "withQuickPromoteEligibilityTweetFields": True}
        if cursor:
            v["cursor"] = cursor
        return self.gql("SearchTimeline", v)


if __name__ == "__main__":
    c = XClient()
    j = c.search('"Virgo Transport 8"', "Latest")
    blob = json.dumps(j)
    print("OK — panjang response:", len(blob), "| objek Tweet:", blob.count('"__typename":"Tweet"'))
