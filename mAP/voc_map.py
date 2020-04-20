# -*- coding: utf-8 -*-

"""
@date: 2020/4/20 下午3:30
@file: voc_map.py
@author: zj
@description: PASCAL VOC版本的mAP计算
"""

import json
import shutil
import os
import glob
import numpy as np

import util
import file


def pretreat(ground_truth_dir, detection_result_dir, tmp_json_dir):
    """
    预处理，保证真值边界框文件与预测边界框的文件一一对应，清空临时文件夹
    :param ground_truth_dir: 目录，保存真值边界框信息
    :param detection_result_dir: 目录，保存预测边界框信息
    :param tmp_json_dir: 临时文件夹
    """
    gt_list = [os.path.splitext(name)[0] for name in os.listdir(ground_truth_dir)]
    dr_list = [os.path.splitext(name)[0] for name in os.listdir(detection_result_dir)]

    if len(gt_list) == len(dr_list) and len(gt_list) == np.sum(
            [True if name in dr_list else False for name in gt_list]):
        pass
    else:
        util.error('真值边界框文件和预测边界框文件没有一一对应')

    if os.path.exists(tmp_json_dir):  # if it exist already
        # reset the tmp directory
        shutil.rmtree(tmp_json_dir)
    os.mkdir(tmp_json_dir)


def parse_ground_truth(ground_truth_dir, tmp_json_dir):
    """
    解析每个图片的真值边界框，以格式{"cate": "cucumber", "bbox": [23, 42, 206, 199], "used": true}保存
    """
    gt_path_list = glob.glob(os.path.join(ground_truth_dir, '*.txt'))

    # 统计每类的真值标注框数量
    gt_per_classes_dict = {}
    for gt_path in gt_path_list:
        json_list = list()
        lines = file.file_lines_to_list(gt_path)
        for line in lines:
            cate, xmin, ymin, xmax, ymax = line.split(' ')
            json_list.append({'cate': cate, 'bbox': [int(xmin), int(ymin), int(xmax), int(ymax)], 'used': False})

            if gt_per_classes_dict.get(cate) is None:
                gt_per_classes_dict[cate] = 1
            else:
                gt_per_classes_dict[cate] += 1
        # 保存
        name = os.path.splitext(os.path.basename(gt_path))[0]
        json_path = os.path.join(tmp_json_dir, name + ".json")
        with open(json_path, 'w') as f:
            json.dump(json_list, f)

    return gt_per_classes_dict


def parse_detection_results(detection_result_dir, tmp_json_dir):
    """
    解析每个类别的预测边界框，以格式{"confidence": "0.999", "file_id": "cucumber_61", "bbox": [16, 42, 225, 163]}保存
    """
    dr_path_list = glob.glob(os.path.join(detection_result_dir, '*.txt'))

    # 保存每个类别的预测边界框信息
    dt_per_classes_dict = dict()
    for dr_path in dr_path_list:
        lines = file.file_lines_to_list(dr_path)
        name = os.path.splitext(os.path.basename(dr_path))[0]

        for line in lines:
            cate, confidence, xmin, ymin, xmax, ymax = line.split(' ')
            if dt_per_classes_dict.get(cate) is None:
                dt_per_classes_dict[cate] = [
                    {'confidence': confidence, 'file_id': name, 'bbox': [int(xmin), int(ymin), int(xmax), int(ymax)]}]
            else:
                dt_per_classes_dict[cate].append(
                    {'confidence': confidence, 'file_id': name, 'bbox': [int(xmin), int(ymin), int(xmax), int(ymax)]})

    # 保存
    for key, value in dt_per_classes_dict.items():
        # 按置信度递减排序
        value.sort(key=lambda x: float(x['confidence']), reverse=True)

        json_path = os.path.join(tmp_json_dir, key + "_dt.json")
        with open(json_path, 'w') as f:
            json.dump(value, f)

    return dt_per_classes_dict


def voc_ap(rec, prec):
    """
    --- Official matlab code VOC2012---
    mrec=[0 ; rec ; 1];
    mpre=[0 ; prec ; 0];
    for i=numel(mpre)-1:-1:1
            mpre(i)=max(mpre(i),mpre(i+1));
    end
    i=find(mrec(2:end)~=mrec(1:end-1))+1;
    ap=sum((mrec(i)-mrec(i-1)).*mpre(i));
    """
    rec.insert(0, 0.0)  # insert 0.0 at begining of list
    rec.append(1.0)  # insert 1.0 at end of list
    mrec = rec[:]
    prec.insert(0, 0.0)  # insert 0.0 at begining of list
    prec.append(0.0)  # insert 0.0 at end of list
    mpre = prec[:]
    """
     This part makes the precision monotonically decreasing
        (goes from the end to the beginning)
        matlab: for i=numel(mpre)-1:-1:1
                    mpre(i)=max(mpre(i),mpre(i+1));
    """
    # matlab indexes start in 1 but python in 0, so I have to do:
    #     range(start=(len(mpre) - 2), end=0, step=-1)
    # also the python function range excludes the end, resulting in:
    #     range(start=(len(mpre) - 2), end=-1, step=-1)
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    """
     This part creates a list of indexes where the recall changes
        matlab: i=find(mrec(2:end)~=mrec(1:end-1))+1;
    """
    i_list = []
    for i in range(1, len(mrec)):
        if mrec[i] != mrec[i - 1]:
            i_list.append(i)  # if it was matlab would be i + 1
    """
     The Average Precision (AP) is the area under the curve
        (numerical integration)
        matlab: ap=sum((mrec(i)-mrec(i-1)).*mpre(i));
    """
    ap = 0.0
    for i in i_list:
        ap += ((mrec[i] - mrec[i - 1]) * mpre[i])
    return ap, mrec, mpre


if __name__ == '__main__':
    ground_truth_dir = './input/ground-truth'
    detection_result_dir = './input/detection-results'
    tmp_json_dir = '.tmp_files'
    pretreat(ground_truth_dir, detection_result_dir, tmp_json_dir)

    # 将.txt文件解析成json格式
    gt_per_classes_dict = parse_ground_truth(ground_truth_dir, tmp_json_dir)
    gt_classes = list(gt_per_classes_dict.keys())
    # let's sort the classes alphabetically
    gt_classes = sorted(gt_classes)
    n_classes = len(gt_classes)
    print(gt_classes)
    print(gt_per_classes_dict)

    dt_per_classes_dict = parse_detection_results(detection_result_dir, tmp_json_dir)

    MIN_OVERLAP = 0.5
    count_true_positives = {}
    # 计算每个类别的tp/fp
    sum_AP = 0.0
    ap_dictionary = {}
    for cate, dt_list in dt_per_classes_dict.items():
        # {cate_1: [], cate2: [], ...}
        nd = len(dt_list)
        tp = [0] * nd  # creates an array of zeros of size nd
        fp = [0] * nd
        # 遍历所有候选预测框，判断TP/FP/FN
        for idx, dt_data in enumerate(dt_list):
            count_true_positives[cate] = 0
            # {"confidence": "0.999", "file_id": "cucumber_61", "bbox": [16, 42, 225, 163]}
            # 读取保存的信息
            file_id = dt_data['file_id']
            dt_bbox = dt_data['bbox']
            confidence = dt_data['confidence']

            # 读取对应文件的真值标注框
            gt_path = os.path.join(tmp_json_dir, file_id + ".json")
            gt_data = json.load(open(gt_path))

            # 逐个计算预测边界框和对应类别的真值标注框的IoU，得到其对应最大IoU的真值标注框
            ovmax = -1
            gt_match = -1
            # load detected object bounding-box
            for obj in gt_data:
                # {"cate": "cucumber", "bbox": [23, 42, 206, 199], "used": true}
                # 读取保存的信息
                obj_cate = obj['cate']
                obj_bbox = obj['bbox']
                obj_used = obj['used']

                # look for a class_name match
                if obj_cate == cate:
                    bi = [max(dt_bbox[0], obj_bbox[0]), max(dt_bbox[1], obj_bbox[1]),
                          min(dt_bbox[2], obj_bbox[2]), min(dt_bbox[3], obj_bbox[3])]
                    iw = bi[2] - bi[0] + 1
                    ih = bi[3] - bi[1] + 1
                    if iw > 0 and ih > 0:
                        # compute overlap (IoU) = area of intersection / area of union
                        ua = (dt_bbox[2] - dt_bbox[0] + 1) * (dt_bbox[3] - dt_bbox[1] + 1) + \
                             (obj_bbox[2] - obj_bbox[0] + 1) * (obj_bbox[3] - obj_bbox[1] + 1) \
                             - iw * ih
                        ov = iw * ih / ua
                        if ov > ovmax:
                            ovmax = ov
                            gt_match = obj
            # 如果大于最小IoU阈值，则进一步判断是否为TP
            if ovmax >= MIN_OVERLAP:
                if not bool(gt_match["used"]):
                    # true positive
                    tp[idx] = 1
                    gt_match["used"] = True
                    count_true_positives[cate] += 1
                    # update the ".json" file
                    with open(gt_path, 'w') as f:
                        json.dump(gt_data, f)
                else:
                    # false positive (multiple detection)
                    fp[idx] = 1
            else:
                # false positive
                fp[idx] = 1

        # compute precision/recall
        cumsum = 0
        for idx, val in enumerate(fp):
            fp[idx] += cumsum
            cumsum += val
        cumsum = 0
        for idx, val in enumerate(tp):
            tp[idx] += cumsum
            cumsum += val

        rec = tp[:]
        for idx, val in enumerate(tp):
            rec[idx] = float(tp[idx]) / gt_per_classes_dict[cate]
        # print(rec)
        prec = tp[:]
        for idx, val in enumerate(tp):
            prec[idx] = float(tp[idx]) / (fp[idx] + tp[idx])
        # print(prec)

        ap, mrec, mprec = voc_ap(rec[:], prec[:])
        sum_AP += ap
        # class_name + " AP = {0:.2f}%".format(ap*100)
        text = "{0:.2f}%".format(ap * 100) + " = " + cate + " AP "
        print(text)
    mAP = sum_AP / n_classes
    text = "mAP = {0:.2f}%".format(mAP * 100)
    print(text)
