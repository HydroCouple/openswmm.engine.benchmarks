// Headless entry point to the GUI's unchanged MeshGenerator, not a second mesher.
#include "mesh/meshgenerator.h"
#include <QCoreApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QTextStream>
#include <algorithm>
#include <cmath>

static QVector<QPointF> points(const QJsonArray &array)
{
    QVector<QPointF> result;
    for (const auto &value : array) {
        const auto p = value.toArray();
        result.append(QPointF(p[0].toDouble(), p[1].toDouble()));
    }
    return result;
}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    if (argc != 3) return 2;
    QFile input(argv[1]);
    if (!input.open(QIODevice::ReadOnly)) return 2;
    QJsonParseError parse;
    const auto doc = QJsonDocument::fromJson(input.readAll(), &parse);
    if (parse.error != QJsonParseError::NoError || !doc.isObject()) return 2;
    const auto request = doc.object();
    mesh::MeshGenerator generator;
    generator.setDomain(QPolygonF(points(request["domain"].toArray())));
    for (const auto &value : request["constraints"].toArray()) {
        const auto item = value.toObject();
        generator.addConstraintSegment({points(item["points"].toArray()),
            item["marker"].toInt(), item["tag"].toString()});
    }
    for (const auto &p : points(request["holes"].toArray())) generator.addHole(p);
    mesh::GenerationOptions options;
    options.maxArea = request["max_area"].toDouble();
    options.minCellSize = request["min_cell_size"].toDouble();
    options.minAngleDeg = 28;
    options.maxCells = 500000;
    options.latticeSeeding = true;
    options.smoothingPasses = 3;
    generator.setOptions(options);
    // Optional graded local refinement uses the GUI's existing size callback.
    const auto boxes = request["refinement_boxes"].toArray();
    if (!boxes.isEmpty()) {
        for (const auto &value : boxes) {
            const auto box = value.toObject();
            for (const auto &key : {"xmin", "xmax", "ymin", "ymax", "max_area", "transition_width"})
                if (!box[key].isDouble() || !std::isfinite(box[key].toDouble())) return 2;
            if (!(options.maxArea > 0.0) || box["xmin"].toDouble() >= box["xmax"].toDouble() ||
                box["ymin"].toDouble() >= box["ymax"].toDouble() ||
                box["max_area"].toDouble() <= 0.0 || box["max_area"].toDouble() > options.maxArea ||
                box["transition_width"].toDouble() <= 0.0) return 2;
        }
        mesh::RefineHook hook;
        hook.targetAreaAt = [boxes, background = options.maxArea](double x, double y) {
            double area = background;
            for (const auto &value : boxes) {
                const auto box = value.toObject();
                const double distance = std::hypot(std::max({box["xmin"].toDouble()-x, 0.0, x-box["xmax"].toDouble()}),
                                                   std::max({box["ymin"].toDouble()-y, 0.0, y-box["ymax"].toDouble()}));
                const double weight = std::clamp(distance / box["transition_width"].toDouble(), 0.0, 1.0);
                const double fine = box["max_area"].toDouble();
                area = std::min(area, fine + weight * (background-fine));
            }
            return area;
        };
        generator.setRefineHook(hook);
    }
    const auto result = generator.generate();
    if (!result.ok || result.hasQuads() || generator.stats().refineCapped) {
        QTextStream(stderr) << result.errorMsg << " refinement capped: "
                            << generator.stats().refineCapped << '\n';
        return 1;
    }
    QJsonArray vertices, cells;
    for (const auto &v : result.vertices) vertices.append(QJsonArray{v.xy.x(), v.xy.y()});
    for (const auto &t : result.triangles) cells.append(QJsonArray{t.v0,t.v1,t.v2});
    const auto &s = generator.stats();
    const QJsonObject stats{{"refine_capped",s.refineCapped},
        {"triangles_below_angle",s.trianglesBelowAngle},
        {"segment_splits",s.segmentSplits}, {"size_inserted",s.sizeInserted},
        {"quality_inserted",s.qualityInserted}};
    QFile output(argv[2]);
    if (!output.open(QIODevice::WriteOnly)) return 2;
    output.write(QJsonDocument(QJsonObject{{"vertices",vertices},{"triangles",cells},
                                         {"stats",stats}}).toJson(QJsonDocument::Compact));
    return 0;
}
