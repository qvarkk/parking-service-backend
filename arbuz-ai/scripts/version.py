from ultralytics import YOLO
import cv2
import numpy as np
import os
import time

ver = ['yolov8x-seg.pt', 'yolov8x-obb.pt']
colors = (
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),  # 1-й ряд
    (255, 0, 255), (0, 255, 255), (128, 0, 0), (0, 128, 0),  # 2-й ряд
    (0, 0, 128), (128, 128, 0), (128, 0, 128), (0, 128, 128),  # 3-й ряд
    (64, 64, 64), (200, 100, 50), (50, 150, 250), (180, 130, 70),  # 4-й ряд
    (100, 200, 100), (70, 70, 200), (30, 200, 200), (200, 200, 200)  # 5-й ряд
)


def process_image(image_path, yolo_ver):
    image = cv2.imread(image_path)
    results = model(image)[0]
    image = results.orig_img.copy()
    classes_names = results.names

    # Проверяем, есть ли маски (для сегментации)
    if hasattr(results, 'masks') and results.masks is not None:
        masks = results.masks.data.cpu().numpy()
        classes = results.boxes.cls.cpu().numpy()

        for i, (mask, class_id) in enumerate(zip(masks, classes)):
            class_name = classes_names[int(class_id)]
            color = colors[int(class_id) % len(colors)]

            # Применяем маску как контур
            mask = cv2.resize(mask, (image.shape[1], image.shape[0]))
            mask_binary = (mask > 0.5).astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Рисуем контур
            cv2.drawContours(image, contours, -1, color, 2)

            # Добавляем текст
            if len(contours) > 0:
                x, y, w, h = cv2.boundingRect(contours[0])
                cv2.putText(image, class_name, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Для OBB (ориентированные рамки)
    elif hasattr(results, 'obb') and results.obb is not None:
        obb_boxes = results.obb.data.cpu().numpy()
        classes = results.obb.cls.cpu().numpy()

        for box, class_id in zip(obb_boxes, classes):
            class_name = classes_names[int(class_id)]
            color = colors[int(class_id) % len(colors)]

            # OBB формат: [x1, y1, x2, y2, x3, y3, x4, y4, confidence, class]
            if len(box) >= 8:
                points = box[:8].reshape(-1, 2).astype(np.int32)
                cv2.polylines(image, [points], True, color, 2)

                # Добавляем текст в центре рамки
                center = np.mean(points, axis=0).astype(np.int32)
                cv2.putText(image, class_name, tuple(center), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Обычные рамки (если нет ни масок, ни OBB)
    else:
        classes = results.boxes.cls.cpu().numpy()
        boxes = results.boxes.xyxy.cpu().numpy().astype(np.int32)

        for class_id, box in zip(classes, boxes):
            class_name = classes_names[int(class_id)]
            color = colors[int(class_id) % len(colors)]
            x1, y1, x2, y2 = box
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            cv2.putText(image, class_name, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    new_image_path = os.path.splitext(image_path)[0] + '_yolo_' + yolo_ver + os.path.splitext(image_path)[1]
    cv2.imwrite(new_image_path, image)
    print(f"Segment saved to {new_image_path}")


full_p = "C:\\Users\\belen\\OneDrive\\Рабочий стол\\parking_dataset\\"

for _ver in ver:
    try:
        model = YOLO(_ver)
    except Exception as e:
        print(e)
        continue
    for i in range(2, 6):
        start_time = time.time()
        process_image(f"{full_p}data{i}.jpg", yolo_ver=_ver)
        end_time = time.time()
        print(f"Версия {_ver}, image {i}: {end_time - start_time:.2f} секунд")