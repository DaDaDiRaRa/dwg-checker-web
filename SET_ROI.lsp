(defun c:SET_ROI ( / blk blkName insPt xscale yscale blkWidth blkHeight p1 p2 p3 p4 p5 p6 pt1 pt2 loop list_rois_str jsonStr file path p7 p8 vs_roi_str)
  (vl-load-com)

  (setq blk (car (entsel "\n기준 도곽 블록을 선택하세요: ")))
  (if (not blk)
    (progn (princ "\n선택 취소됨.") (exit))
  )

  (setq blkName (cdr (assoc 2 (entget blk))))
  (setq insPt (cdr (assoc 10 (entget blk))))
  (setq xscale (abs (cdr (assoc 41 (entget blk)))))
  (setq yscale (abs (cdr (assoc 42 (entget blk)))))

  ;; 도곽 원본 크기 추출 (바운딩 박스)
  (vla-GetBoundingBox (vlax-ename->vla-object blk) 'minPt 'maxPt)
  (setq blkWidth  (/ (- (car (vlax-safearray->list maxPt)) (car (vlax-safearray->list minPt))) xscale))
  (setq blkHeight (/ (- (cadr (vlax-safearray->list maxPt)) (cadr (vlax-safearray->list minPt))) yscale))

  (princ (strcat "\n블록 이름: " blkName))

  ;; 1. 개별 도면용 박스 지정
  (princ "\n[개별 도면 파싱용]")
  (setq p1 (getpoint "\n도면번호 구역 첫 번째 구석점: "))
  (setq p2 (getcorner p1 "\n도면번호 구역 반대편 구석점: "))

  (setq p3 (getpoint "\n도면명 구역 첫 번째 구석점: "))
  (setq p4 (getcorner p3 "\n도면명 구역 반대편 구석점: "))

  (setq p5 (getpoint "\n축척 구역 첫 번째 구석점: "))
  (setq p6 (getcorner p5 "\n축척 구역 반대편 구석점: "))

  ;; 2. 뷰 심볼(원+선) 탐색 영역 지정 (선택 사항)
  ;; ※ 이 단계는 목록표 단(Column) 루프보다 먼저 와야 합니다.
  ;;   (루프 탈출 Enter 입력이 다음 getpoint로 흘러들어가는 현상 방지)
  (princ "\n\n[뷰 심볼(원+선) 탐색용]")
  (princ "\n도면 내부의 원+선 제목 기호들이 포함된 영역 전체를 박스로 지정하세요.")
  (princ "\n(없으면 Enter로 건너뜁니다)")
  (setq vs_roi_str "null")
  (setq p7 (getpoint "\n첫 번째 구석점 (Enter = 건너뜀): "))
  (if p7
    (progn
      (setq p8 (getcorner p7 "\n반대편 구석점: "))
      (if p8
        (progn
          ;; 비율 계산 (인라인 - calc-roi 정의 전에 실행되므로 직접 계산)
          (setq vx1 (/ (- (car p7) (car insPt)) (* blkWidth xscale)))
          (setq vx2 (/ (- (car p8) (car insPt)) (* blkWidth xscale)))
          (setq vy1 (/ (- (cadr p7) (cadr insPt)) (* blkHeight yscale)))
          (setq vy2 (/ (- (cadr p8) (cadr insPt)) (* blkHeight yscale)))
          (setq vs_roi_str (strcat "[" (rtos (min vx1 vx2) 2 5) ", " (rtos (max vx1 vx2) 2 5) ", " (rtos (min vy1 vy2) 2 5) ", " (rtos (max vy1 vy2) 2 5) "]"))
          (princ "\n▶ 뷰 심볼 영역 지정 완료!")
        )
      )
    )
  )

  ;; 3. 도면목록표용 다단(Multi-Column) 박스 지정
  (princ "\n\n[도면목록표 파싱용]")
  (princ "\n목록표의 단(Column)을 순서대로 지정하세요. (완료 시 허공에 우클릭 또는 Enter)")

  (setq loop T)
  (setq list_rois_str "")

  (while loop
    (setq pt1 (getpoint "\n목록표 단(Column) 첫 번째 구석점 (완료: 우클릭): "))
    (if pt1
      (progn
        (setq pt2 (getcorner pt1 "\n목록표 단(Column) 반대편 구석점: "))
        (if pt2
          (progn
            ;; 좌표 비율 계산
            (setq lx1 (/ (- (car pt1) (car insPt)) (* blkWidth xscale)))
            (setq lx2 (/ (- (car pt2) (car insPt)) (* blkWidth xscale)))
            (setq ly1 (/ (- (cadr pt1) (cadr insPt)) (* blkHeight yscale)))
            (setq ly2 (/ (- (cadr pt2) (cadr insPt)) (* blkHeight yscale)))

            ;; 문자열 만들기 "[min_x, max_x, min_y, max_y]"
            (setq cur_roi (strcat "[" (rtos (min lx1 lx2) 2 5) ", " (rtos (max lx1 lx2) 2 5) ", " (rtos (min ly1 ly2) 2 5) ", " (rtos (max ly1 ly2) 2 5) "]"))

            (if (= list_rois_str "")
              (setq list_rois_str cur_roi)
              (setq list_rois_str (strcat list_rois_str ", " cur_roi))
            )
            (princ "\n▶ 해당 단(Column) 지정 완료!")
          )
        )
      )
      (setq loop nil) ;; 우클릭 시 루프 탈출
    )
  )

  ;; 비율 계산 함수 (p1~p6 JSON 조합용)
  (defun calc-roi (ptA ptB)
    (setq nx1 (/ (- (car ptA) (car insPt)) (* blkWidth xscale)))
    (setq nx2 (/ (- (car ptB) (car insPt)) (* blkWidth xscale)))
    (setq ny1 (/ (- (cadr ptA) (cadr insPt)) (* blkHeight yscale)))
    (setq ny2 (/ (- (cadr ptB) (cadr insPt)) (* blkHeight yscale)))
    (strcat "[" (rtos (min nx1 nx2) 2 5) ", " (rtos (max nx1 nx2) 2 5) ", " (rtos (min ny1 ny2) 2 5) ", " (rtos (max ny1 ny2) 2 5) "]")
  )

  ;; JSON 텍스트 조합
  (setq jsonStr
    (strcat
      "{\n"
      "  \"base_w\": " (rtos blkWidth 2 5) ",\n"
      "  \"base_h\": " (rtos blkHeight 2 5) ",\n"
      "  \"num_roi\": " (calc-roi p1 p2) ",\n"
      "  \"title_roi\": " (calc-roi p3 p4) ",\n"
      "  \"scale_roi\": " (calc-roi p5 p6) ",\n"
      "  \"list_rois\": [" list_rois_str "],\n"
      "  \"view_symbol_roi\": " vs_roi_str "\n"
      "}"
    )
  )

  ;; 파일 저장 경로 세팅 (AppData 폴더 활용)
  (setq path (strcat (getenv "APPDATA") "\\AutoDWG_Checker"))
  (vl-mkdir path)
  (setq file (open (strcat path "\\" blkName ".json") "w"))

  (write-line jsonStr file)
  (close file)

  (princ (strcat "\n\n[성공] 도곽 설정이 저장되었습니다! (" blkName ".json)"))
  (princ "\n파이썬 검토기를 실행해주세요.\n")
  (princ)
)
