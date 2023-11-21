import json
from typing import Iterable

import scrapy
from scrapy import Request


class TripsSpider(scrapy.Spider):
    name = 'trips'
    allowed_domains = ['www.intrepidtravel.com']

    def __init__(self, links_path=None, *args, **kwargs):
        super(TripsSpider, self).__init__(*args, **kwargs)
        self._link_file = links_path

    def start_requests(self) -> Iterable[Request]:
        if not self._link_file:
            raise ValueError("Please provide a link file")
        with open(self._link_file, "r") as f:
            links = f.readlines()
        links = [link.strip() for link in links]
        for link in links:
            yield Request(
                url=link,
                callback=self.parse
            )

    @staticmethod
    def _normalize_text(text) -> str:
        if not text:
            return ""
        if not isinstance(text, str):
            return text
        t = text.strip().replace("\n", " ").replace("\r", " ")
        # remove duplicate spaces
        while "  " in t:
            t = t.replace("  ", " ")
        return t

    def parse(self, response, **kwargs):
        title = self._parse_title(response)
        trip_snapshot = self._parse_trip_snapshot(response)
        gallery = self._parse_gallery(response)
        summary = self._parse_summary(response)
        trip_overview = self._parse_trip_overview(response)
        wyltt = self._parse_why_you_love_this_trip(response)
        ittrfy = self._parse_is_this_trip_right_for_you(response)
        itinerary = self._parse_itinerary(response)
        inclusions = self._parse_inclusions(response)
        important_notes = self._parse_important_notes(response)
        trip_code = trip_overview.get("trip_code")

        item = {"title": title, "snapshot": trip_snapshot, "gallery": gallery, "summary": summary,
                "trip_overview": trip_overview, "why_you_love_this_trip": wyltt, "is_this_trip_right_for_you": ittrfy,
                "itinerary": itinerary,
                "inclusions": inclusions,
                "important_notes": important_notes}
        yield scrapy.Request(
            url=f"https://www.intrepidtravel.com/uk/ajax/peak-shortcode-review/get-reviews?limit=10&page=1&product_code={trip_code}",
            callback=self._crawl_trip_reviews,
            meta={"item": item, "page": 1, "limit": 10}
        )

    def _parse_trip_snapshot(self, response):
        trip_snapshot = response.css(".trip-snapshot")
        heading = self._normalize_text(trip_snapshot.css("h2 ::text").get())
        review_aggregate_div = trip_snapshot.css(".review-aggregate")
        review_aggregate = {
            "rating": None,
            "avg": None,
            "summary": None
        }
        if review_aggregate_div:
            review_aggregate = {
                "rating": self._normalize_text(review_aggregate_div.css("span.rating").attrib["aria-label"]),
                "avg": self._normalize_text(
                    review_aggregate_div.css("div[data-cy = 'review-average'] span::text").get()),
                "summary": self._normalize_text(review_aggregate_div.css("div[data-cy = 'review-average']::text").get())
            },

        themes = trip_snapshot.css(".trip-snapshot__themes div[data-cy = 'chip']::text").getall()
        themes = [self._normalize_text(theme) for theme in themes]
        return {
            "heading": heading,
            "review_aggregate": review_aggregate,
            "themes": themes,
            "price": {
                "currency": self._normalize_text(
                    trip_snapshot.css(".price [data-cy = 'price-currency-code']::text").get()),
                "value": self._normalize_text(trip_snapshot.css(".price [data-cy = 'price-value']::text").get()),
            }
        }

    def _parse_title(self, response):
        title = self._normalize_text(response.css(".page-banner h1 ::text").get())
        return title

    @staticmethod
    def _parse_gallery(response):
        gallery = response.css("[data-cy = 'trip-gallery']")
        relative_images = gallery.css(".gallery__image-frame img::attr(src)").getall()
        images = []
        for relative_image in relative_images:
            images.append(response.urljoin(relative_image))
        return images

    def _parse_summary(self, response):
        return self._normalize_text(response.css("#trip-summary p::text").get())

    @staticmethod
    def _parse_itinerary(response):
        result = []
        itinerary = response.css("#itinerary")
        days = itinerary.css("div[data-cy = 'trip-itinerary-day']")
        for day in days:
            header = day.css("button b::text").get()
            summary = day.css('[data-cy="accordion-body"]').xpath("./div/div[1]//text()").get()
            special_information = day.css('[data-cy="accordion-body"]').xpath("./div/div[3]").css(
                ".rich-text p::text").get()
            metadata_parsed = []
            list_metadata = day.css(".trip-itinerary-day__meta-data-section").css(".l-grid__cell .l-grid__cell--12-col")
            for metadata in list_metadata:
                key = metadata.xpath("./div[1]//text()").getall()[-1].strip()
                value = [m.strip() for m in metadata.css("ul li::text").getall()]
                value.extend([m.strip() for m in metadata.css("p::text").getall()])
                metadata_parsed.append({key: value})
            result.append({
                "header": header,
                "summary": summary,
                "metadata": metadata_parsed,
                "special_information": special_information
            })

        return result

    @staticmethod
    def _parse_inclusion(inclusion):
        raw_li = inclusion.css('.tile__content ul li::text').getall()
        p = [p.strip() for p in raw_li]
        raw_p = inclusion.css('.tile__content p::text').getall()
        li = [li.strip() for li in raw_p]
        return p + li

    def _parse_inclusions(self, response):
        result = {}
        inclusions = response.css("#inclusions")
        meals = self._parse_inclusion(inclusions.css('[data-cy="trip-inclusions-meals"]'))
        transport = self._parse_inclusion(inclusions.css('[data-cy="trip-inclusions-transport"]'))
        accommodation = self._parse_inclusion(inclusions.css('[data-cy="trip-inclusions-accommodation"]'))
        activities = self._parse_inclusion(inclusions.css('[data-cy="trip-inclusions-activities"]'))
        optional_activities = self._parse_inclusion(inclusions.css('[data-cy="trip-inclusions-optional-activities"]'))

        result["meals"] = meals
        result["transport"] = transport
        result["accommodation"] = accommodation
        result["activities"] = activities
        result["optional_activities"] = optional_activities
        return result

    @staticmethod
    def _parse_important_notes(response):
        return [p.strip() for p in response.css("#important-notes").css("p::text").getall()]

    @staticmethod
    def _parse_is_this_trip_right_for_you(response):
        result = []
        ittrfy = response.css("#ITTRFY")
        result.extend(ittrfy.css("[data-cy='ittrfy__description']").css('ul li::text').getall())
        result.extend(ittrfy.css("[data-cy='ittrfy__description']").css('p::text').getall())
        return result

    @staticmethod
    def _parse_why_you_love_this_trip(response):
        result = []
        ittrfy = response.css("#WYLTT")
        result.extend(ittrfy.css("[data-cy='wyltt__description']").css('ul li::text').getall())
        result.extend(ittrfy.css("[data-cy='wyltt__description']").css('p::text').getall())
        return result

    def _parse_trip_overview(self, response):
        overview = response.css("#trip-overview")
        map_img_path = overview.css("[data-cy='trip-summary__map']").attrib["src"].split("?")[0]
        map_img_url = response.urljoin(map_img_path)
        dictionary = overview.css('[data-cy="trip-summary__dictionary-grid"]')
        dictionary_parsed = {}
        list_dt = dictionary.css("dt")
        trip_code = None
        for dt in list_dt:
            key = dt.css("::text").get()
            next_dd = dt.xpath("./following-sibling::dd[1]")
            if key.lower() not in ["destinations", "physical rating"]:
                value = next_dd.css("::text").get().strip()
                dictionary_parsed[key] = value
                if key.lower() == "trip code":
                    trip_code = value
                continue
            if key.lower() == "destinations":
                dest_names = next_dd.css("span a::text").getall()
                dest_urls = next_dd.css("span a::attr(href)").getall()
                list_dest = dict(zip(dest_names, dest_urls))
                dictionary_parsed[key] = list_dest
                continue
            if key.lower() == "physical rating":
                value = next_dd.css('[data-cy="rating"]::attr(aria-label)').get()
                dictionary_parsed[key] = value
                continue
        return {
            "trip_code": trip_code,
            "map_img_url": map_img_url,
            "dictionary": dictionary_parsed
        }

    def _crawl_trip_reviews(self, response):
        api_data = json.loads(response.text)
        reviews = api_data["reviews"]
        finished = len(reviews) == 0
        item = response.meta["item"]
        if "reviews" not in item:
            item["reviews"] = []
        if finished:
            yield item
        else:
            item["reviews"].extend(reviews)
            page = response.meta["page"]
            limit = response.meta["limit"]
            page += 1
            yield scrapy.Request(
                url=f"https://www.intrepidtravel.com/uk/ajax/peak-shortcode-review/get-reviews?limit={limit}&page={page}&product_code={item['trip_overview']['trip_code']}",
                callback=self._crawl_trip_reviews,
                meta={"item": item, "page": page, "limit": limit}
            )
