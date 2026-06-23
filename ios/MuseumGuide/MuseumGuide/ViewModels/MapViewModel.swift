import SwiftUI

@Observable
final class MapViewModel {
    var selectedFloor: FloorDTO?
    var currentMuseum: MuseumDetailDTO?

    func bind(museum: MuseumDetailDTO) {
        currentMuseum = museum
        if selectedFloor == nil { selectedFloor = museum.floors.first }
    }
}
