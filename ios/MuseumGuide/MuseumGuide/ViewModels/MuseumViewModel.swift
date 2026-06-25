import SwiftUI

@Observable
final class MuseumViewModel {
    var currentMuseum: MuseumDetailDTO?
    var isLoading = false
    var errorMessage: String?

    var selectedFloorId: Int?
    var exhibits: [ExhibitListItem] = []
    var isLoadingExhibits = false

    // 博物馆列表
    var museums: [MuseumListItemDTO] = []

    let api = APIClient.shared
    let location = LocationManager.shared

    /// 加载支持的博物馆列表
    func loadMuseumList() async {
        do {
            let resp = try await api.museumList()
            museums = resp.museums
        } catch {
            print("博物馆列表加载失败: \(error)")
        }
    }

    /// 选择某个博物馆并加载详情
    func selectMuseum(id: Int) {
        Task {
            do {
                currentMuseum = try await api.museumDetail(id: id)
                if let firstFloor = currentMuseum?.floors.first {
                    selectedFloorId = firstFloor.id
                    await loadExhibits(museumId: id, floorId: firstFloor.id)
                }
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    /// 定位失败时手动加载（用于体验/调试）
    func loadTestMuseum() {
        selectMuseum(id: 1)
    }

    func switchFloor(_ floorId: Int) {
        guard let museum = currentMuseum else { return }
        selectedFloorId = floorId
        Task { await loadExhibits(museumId: museum.id, floorId: floorId) }
    }

    func loadExhibits(museumId: Int, floorId: Int) async {
        isLoadingExhibits = true
        defer { isLoadingExhibits = false }
        do {
            let resp = try await api.exhibitList(museumId: museumId, floorId: floorId)
            exhibits = resp.exhibits
        } catch {
            print("展品列表加载失败: \(error)")
        }
    }

    var locatedMuseumId: Int?

    func loadCurrentMuseum() async {
        isLoading = true
        errorMessage = nil
        do {
            let coord = try await location.getCurrentLocation()
            let locateResp = try await api.locate(lat: coord.latitude, lng: coord.longitude)
            guard locateResp.isInside, let museumId = locateResp.museumId else {
                isLoading = false
                return
            }
            locatedMuseumId = museumId
            // 定位成功 → 直接进博物馆详情
            currentMuseum = try await api.museumDetail(id: museumId)
            if let firstFloor = currentMuseum?.floors.first {
                selectedFloorId = firstFloor.id
                await loadExhibits(museumId: museumId, floorId: firstFloor.id)
            }
        } catch {
            // 定位失败 → 留在列表页
        }
        isLoading = false
    }
}
