# Late API Support Ticket

**Subject:** Duplicate Instagram Posts - Internal Endpoint Triggering Unexpectedly

---

Hi Late Support Team,

I'm experiencing a critical issue where Instagram posts are being published twice through your platform. After extensive debugging, I've identified the root cause and wanted to share the details.


## Issue Summary

When I send a post via `POST /api/v1/posts`, the request completes successfully with HTTP 200. However, approximately 1 minute later, your internal system automatically triggers a second publish via `POST /api/internal/publish-single-platform`, resulting in duplicate posts on Instagram.

This affects all post types: carousels, reels, and single image posts.


## Evidence

I captured both requests in your Logs panel. Here's a carousel example:

First request at Feb 3, 2026 17:02:31:
- Endpoint: `POST /api/v1/posts`
- Status: 200
- Instagram Post ID: 17847556563642272
- Log ID: 6981fff79ce59127ab8c00d9

Second request at Feb 3, 2026 17:03:45:
- Endpoint: `POST /api/internal/publish-single-platform`
- Status: 200
- Instagram Post ID: 18111250564647736
- Log ID: 698200416355bd8c78e36ccb

Both requests share the same Late Post ID: `6981ffa09ce59127ab8beeda`

The second request was not initiated by my application. I only call `/api/v1/posts`.


## Additional Context

I tested the exact same code with a different Late account connected to a different Instagram account, and the duplicate does not occur. This confirms the issue is specific to this account's configuration or state.

I've thoroughly checked Settings, Integrations, Webhooks, and Publishing options. There are no active integrations or webhooks that could trigger this behavior.

We've also experienced some parameter validation issues with Instagram posting recently (aspect ratio, media format errors). I'm not sure if these are related, but wanted to mention in case there were recent changes to the Instagram publishing flow.


## Account Details

Account ID: 69779d2577637c5c857c815c
Platform: Instagram
Affected Content Types: Carousel, Reels, Single Image


## Questions

What triggers `/api/internal/publish-single-platform` after a successful `/api/v1/posts` call?

Is there a queue, scheduler, or retry mechanism that could be causing this?

Is there an account-level setting, flag, or corrupted state that might be enabling this behavior?

Can you check if there's something different about this account compared to others?


## Impact

This is a production issue affecting our clients. Duplicate posts damage brand credibility and require manual cleanup after every publish. We need to understand the cause and find a solution as soon as possible.

Looking forward to your response.

Best regards,
[YOUR NAME]
[COMPANY/PROJECT NAME]
[EMAIL]
