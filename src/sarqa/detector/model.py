"""Faster R-CNN (ResNet-50 FPN) with a 2-class head and batched prediction."""

import numpy as np
import torch
from torchvision.models.detection import FasterRCNN_ResNet50_FPN_Weights, fasterrcnn_resnet50_fpn
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor


def build_model(cfg: dict, pretrained: bool) -> torch.nn.Module:
    """`pretrained=True` starts from the torchvision COCO detection weights (SPEC §2/§4.3);
    HRSID-trained weights are never used. The box head is replaced by a background+ship head."""
    weights = FasterRCNN_ResNet50_FPN_Weights.COCO_V1 if pretrained else None
    model = fasterrcnn_resnet50_fpn(
        weights=weights, weights_backbone=None,
        min_size=cfg["min_size"], max_size=cfg["max_size"],
        box_score_thresh=cfg["raw_score_thresh"], box_nms_thresh=cfg["nms_iou"],
        box_detections_per_img=cfg["detections_per_img"],
    )
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, 2)
    return model


@torch.no_grad()
def predict(model, loader, device, amp: bool = True) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """file name -> (boxes[N,4] xyxy, scores[N]) for every image the loader yields."""
    model.eval()
    out = {}
    for imgs, _, names in loader:
        imgs = [i.to(device, non_blocking=True) for i in imgs]
        with torch.autocast(device_type=device.type, enabled=amp and device.type == "cuda"):
            res = model(imgs)
        for name, r in zip(names, res, strict=True):
            out[name] = (r["boxes"].float().cpu().numpy(), r["scores"].float().cpu().numpy())
    return out
