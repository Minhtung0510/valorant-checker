import asyncio
import logging
import httpx
from typing import Optional

logger = logging.getLogger("valorant_checker")
_NOPECHA_SUBMIT_LOCK = asyncio.Lock()

class NopechaSolver:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.nopecha.com"

    async def solve_hcaptcha(
        self,
        sitekey: str,
        url: str,
        timeout: int = 120,
        rqdata: str = "",
        useragent: str = "",
        proxy: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Sends an hCaptcha challenge to NopeCHA API and polls for the solution token.
        """
        if not self.api_key:
            logger.error("NopeCHA API Key is missing.")
            return None

        # Step 1: Submit the CAPTCHA
        submit_url = f"{self.base_url}/token/"
        payload = {
            "key": self.api_key,
            "type": "hcaptcha",
            "sitekey": sitekey,
            "url": url
        }
        if rqdata:
            payload["data"] = {"rqdata": rqdata}
        if useragent:
            payload["useragent"] = useragent
        if proxy:
            payload["proxy"] = proxy

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                async with _NOPECHA_SUBMIT_LOCK:
                    logger.info(
                        f"Submitting hCaptcha challenge to NopeCHA "
                        f"(Sitekey: {sitekey}, rqdata={'yes' if rqdata else 'no'}, "
                        f"proxy={'yes' if proxy else 'no'}, useragent={'yes' if useragent else 'no'})"
                    )
                    r = await client.post(submit_url, json=payload)
                    await asyncio.sleep(2)
                if r.status_code != 200:
                    logger.error(f"Failed to submit to NopeCHA: HTTP {r.status_code} - {r.text}")
                    return None
                
                data = r.json()
                if data.get("error") or data.get("code"):
                    logger.error(f"NopeCHA rejected hCaptcha job: {data}")
                    return None

                job_id = data.get("data")
                if not job_id:
                    logger.error(f"NopeCHA response did not contain job ID: {data}")
                    return None

                logger.info(f"hCaptcha submitted successfully. Job ID: {job_id}. Polling for solution...")

                # Step 2: Poll for the solution
                poll_url = f"{self.base_url}/token"
                params = {
                    "key": self.api_key,
                    "id": job_id
                }

                start_time = asyncio.get_event_loop().time()
                while (asyncio.get_event_loop().time() - start_time) < timeout:
                    await asyncio.sleep(3)
                    poll_resp = await client.get(poll_url, params=params)
                    
                    if poll_resp.status_code == 200:
                        poll_data = poll_resp.json()
                        if poll_data.get("error") or poll_data.get("code"):
                            logger.debug(f"NopeCHA hCaptcha job is not ready or failed: {poll_data}")
                            continue

                        token = poll_data.get("data")
                        if token:
                            logger.info("NopeCHA successfully solved hCaptcha!")
                            return token
                    elif poll_resp.status_code == 409:
                        # 409 Conflict typically means job is still processing
                        logger.debug("NopeCHA is still solving the CAPTCHA...")
                    else:
                        logger.warning(f"Unexpected status from NopeCHA polling: HTTP {poll_resp.status_code} - {poll_resp.text}")

                logger.error("NopeCHA hCaptcha solving timed out.")
                return None

        except Exception as e:
            logger.error(f"Error communicating with NopeCHA API: {e}")
            return None
