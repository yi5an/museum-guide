import SwiftUI

@Observable
final class MuseumViewModel {
    var currentMuseum: MuseumDetailDTO?
    var isLoading = false
    var errorMessage: String?

    let api = APIClient.shared
    let location = LocationManager.shared

    func loadCurrentMuseum() async {
        isLoading = true
        errorMessage = nil
        do {
            let coord = try await location.getCurrentLocation()
            let locateResp = try await api.locate(lat: coord.latitude, lng: coord.longitude)
            guard locateResp.isInside, let museumId = locateResp.museumId else {
                errorMessage = "未定位到博物馆，请手动选择"
                isLoading = false
                return
            }
            currentMuseum = try await api.museumDetail(id: museumId)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
