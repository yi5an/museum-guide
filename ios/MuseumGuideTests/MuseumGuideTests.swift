import Testing
import Foundation
@testable import MuseumGuide

@Test func testDecodeNarrateResponse() throws {
    let json = """
    {
        "tier": 1,
        "content": {"blocks": [{"type": "text", "section": "历史", "text": "测试"}]},
        "source_label": "官方",
        "audio_url": null
    }
    """.data(using: .utf8)!

    let resp = try JSONDecoder().decode(NarrateResponse.self, from: json)
    #expect(resp.tier == 1)
    #expect(resp.sourceLabel == "官方")
    #expect(resp.content.blocks.count == 1)
    #expect(resp.content.blocks[0].section == "历史")
}

@Test func testDecodeRecognizeResponse() throws {
    let json = """
    {
        "candidates": [{"exhibit_id": 1, "name": "司母戊鼎", "confidence": 0.92}],
        "best_match": {"exhibit_id": 1, "name": "司母戊鼎", "confidence": 0.92},
        "best_confidence": 0.92
    }
    """.data(using: .utf8)!

    let resp = try JSONDecoder().decode(RecognizeResponse.self, from: json)
    #expect(resp.bestMatch?.name == "司母戊鼎")
    #expect(resp.bestConfidence == 0.92)
    #expect(resp.candidates.count == 1)
}

@Test func testDecodeMuseumDetail() throws {
    let json = """
    {
        "id": 1,
        "name": "中国国家博物馆",
        "name_i18n": {"zh": "中国国家博物馆"},
        "city": "北京",
        "country": "中国",
        "description": "国家级博物馆",
        "floors": [{"id": 1, "level": 2, "name": "F2 青铜厅", "floor_plan_url": null, "sort_order": 2}],
        "routes": [{"id": 1, "title": "精华路线", "theme": "精选", "duration_min": 60, "exhibit_order": [1,2,3]}],
        "exhibit_count": 3
    }
    """.data(using: .utf8)!

    let resp = try JSONDecoder().decode(MuseumDetailDTO.self, from: json)
    #expect(resp.name == "中国国家博物馆")
    #expect(resp.floors.count == 1)
    #expect(resp.floors[0].level == 2)
    #expect(resp.exhibitCount == 3)
}
