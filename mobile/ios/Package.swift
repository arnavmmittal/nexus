// swift-tools-version: 5.9
// This file describes the Swift package structure for the Jarvis iOS project.
// For Xcode project setup, see README.md.

import PackageDescription

let package = Package(
    name: "Jarvis",
    platforms: [
        .iOS(.v17),
        .watchOS(.v10),
    ],
    products: [
        .library(name: "JarvisCore", targets: ["JarvisCore"]),
    ],
    targets: [
        .target(
            name: "JarvisCore",
            path: "Jarvis/Services"
        ),
    ]
)
