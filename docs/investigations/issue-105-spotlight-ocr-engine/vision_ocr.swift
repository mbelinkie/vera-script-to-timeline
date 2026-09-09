import Foundation
import ImageIO
import Vision

struct PixelRect: Codable {
    let x: Int
    let y: Int
    let width: Int
    let height: Int
}

struct Element: Codable {
    let text: String
    let rect: PixelRect
    let rawOrdinal: Int
    let readingOrder: Int
    let lineRawOrdinal: Int?
    let confidenceMillionths: Int?
}

struct OcrOutput: Codable {
    let candidate: String
    let profile: String
    let rasterWidth: Int
    let rasterHeight: Int
    let words: [Element]
    let lines: [Element]
}

struct LanguageOutput: Codable {
    let revision: Int
    let accurate: [String]
    let fast: [String]
}

enum ProbeError: Error, CustomStringConvertible {
    case usage
    case imageLoad(String)
    case invalidGeometry(CGRect)
    case missingWordGeometry(String)

    var description: String {
        switch self {
        case .usage:
            return "usage: vision_ocr <image.png> | --languages"
        case let .imageLoad(path):
            return "could not load image: \(path)"
        case let .invalidGeometry(rect):
            return "invalid Vision geometry: \(rect)"
        case let .missingWordGeometry(word):
            return "Vision returned no geometry for recognized word: \(word)"
        }
    }
}

func encode<T: Encodable>(_ value: T) throws {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
    FileHandle.standardOutput.write(try encoder.encode(value))
    FileHandle.standardOutput.write(Data("\n".utf8))
}

func pixelRect(_ normalized: CGRect, width: Int, height: Int) throws -> PixelRect {
    let left = Int(floor(normalized.minX * Double(width)))
    let top = Int(floor((1.0 - normalized.maxY) * Double(height)))
    let right = Int(ceil(normalized.maxX * Double(width)))
    let bottom = Int(ceil((1.0 - normalized.minY) * Double(height)))
    guard left >= 0, top >= 0, right <= width, bottom <= height,
          right > left, bottom > top else {
        throw ProbeError.invalidGeometry(normalized)
    }
    return PixelRect(x: left, y: top, width: right - left, height: bottom - top)
}

func sortedWithReadingOrder(_ elements: [(String, PixelRect, Int, Int?, Int?)]) -> [Element] {
    elements.sorted {
        if $0.1.y != $1.1.y { return $0.1.y < $1.1.y }
        if $0.1.x != $1.1.x { return $0.1.x < $1.1.x }
        return $0.2 < $1.2
    }.enumerated().map { order, item in
        Element(
            text: item.0,
            rect: item.1,
            rawOrdinal: item.2,
            readingOrder: order,
            lineRawOrdinal: item.3,
            confidenceMillionths: item.4
        )
    }
}

func supportedLanguages() throws {
    let revision = VNRecognizeTextRequestRevision3
    let accurateRequest = VNRecognizeTextRequest()
    accurateRequest.revision = revision
    accurateRequest.recognitionLevel = .accurate
    let accurate = try accurateRequest.supportedRecognitionLanguages().sorted()
    let fastRequest = VNRecognizeTextRequest()
    fastRequest.revision = revision
    fastRequest.recognitionLevel = .fast
    let fast = try fastRequest.supportedRecognitionLanguages().sorted()
    try encode(LanguageOutput(revision: revision, accurate: accurate, fast: fast))
}

func recognize(_ path: String) throws {
    let url = URL(fileURLWithPath: path)
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw ProbeError.imageLoad(path)
    }

    let width = image.width
    let height = image.height
    let request = VNRecognizeTextRequest()
    request.revision = VNRecognizeTextRequestRevision3
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US"]
    request.automaticallyDetectsLanguage = false
    request.usesLanguageCorrection = false
    request.customWords = []
    request.minimumTextHeight = 0

    let handler = VNImageRequestHandler(cgImage: image, orientation: .up, options: [:])
    try handler.perform([request])

    var rawLines: [(String, PixelRect, Int, Int?, Int?)] = []
    var rawWords: [(String, PixelRect, Int, Int?, Int?)] = []
    var wordOrdinal = 0

    for (lineOrdinal, observation) in (request.results ?? []).enumerated() {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let lineRect = try pixelRect(observation.boundingBox, width: width, height: height)
        rawLines.append((
            candidate.string,
            lineRect,
            lineOrdinal,
            nil,
            Int((candidate.confidence * 1_000_000).rounded())
        ))

        candidate.string.enumerateSubstrings(
            in: candidate.string.startIndex..<candidate.string.endIndex,
            options: [.byWords, .substringNotRequired]
        ) { _, range, _, _ in
            do {
                guard let box = try candidate.boundingBox(for: range) else {
                    throw ProbeError.missingWordGeometry(String(candidate.string[range]))
                }
                let rect = try pixelRect(box.boundingBox, width: width, height: height)
                rawWords.append((
                    String(candidate.string[range]),
                    rect,
                    wordOrdinal,
                    lineOrdinal,
                    nil
                ))
                wordOrdinal += 1
            } catch {
                fputs("\(error)\n", stderr)
                exit(2)
            }
        }
    }

    try encode(OcrOutput(
        candidate: "apple-vision",
        profile: "vision-r3-accurate-en-US-no-language-correction-v1",
        rasterWidth: width,
        rasterHeight: height,
        words: sortedWithReadingOrder(rawWords),
        lines: sortedWithReadingOrder(rawLines)
    ))
}

do {
    guard CommandLine.arguments.count == 2 else { throw ProbeError.usage }
    if CommandLine.arguments[1] == "--languages" {
        try supportedLanguages()
    } else {
        try recognize(CommandLine.arguments[1])
    }
} catch {
    fputs("\(error)\n", stderr)
    exit(1)
}
