from core.models import ConfidenceScore


ACTION_KEYWORDS = {
    "tạo", "sửa", "xóa", "thêm", "chạy", "run", "viết", "ghi", "đọc",
    "fix", "create", "add", "delete", "install", "config", "setup",
    "làm", "build", "deploy", "tìm", "đổi", "chỉnh", "code", "debug",
    "refactor", "rename", "move", "copy", "update", "upgrade",
}

FILE_KEYWORDS = {
    ".py", ".js", ".ts", ".html", ".css", ".json", ".toml",
    ".txt", ".md", ".vue", ".tsx", ".jsx", ".java", ".go", ".rs",
    ".cpp", ".h", ".c", ".cs", ".rb", ".php", ".swift", ".kt",
}

SPECIFIC_ACTION_KEYWORDS = {
    "tạo file", "create file", "viết hàm", "sửa lỗi", "fix bug",
    "thêm tính năng", "add feature", "xóa dòng", "delete line",
    "chạy lệnh", "run command", "cài đặt", "install",
}

CLARIFICATION_NEEDED_KEYWORDS = {
    "giúp", "help", "làm sao", "how to", "có thể", "can you",
    "cho hỏi", "hỏi", "question", "tư vấn", "advise",
}


class ConfidenceScorer:
    def score_request(self, prompt: str, context: str = "") -> ConfidenceScore:
        p = prompt.strip().lower()
        words = p.split()
        word_count = len(words)
        char_count = len(p)

        has_action = any(kw in p for kw in ACTION_KEYWORDS)
        has_file = any(pat in p for pat in FILE_KEYWORDS)
        has_specific = any(pat in p for pat in SPECIFIC_ACTION_KEYWORDS)
        has_clarification = any(pat in p for pat in CLARIFICATION_NEEDED_KEYWORDS)
        has_context = bool(context and len(context) > 100)

        reasons = []
        score = 0

        # Base score: word count
        if word_count <= 3:
            score = 5
            reasons.append(f"Chỉ {word_count} từ, không đủ thông tin")
        elif word_count <= 5:
            score = 15
            reasons.append(f"{word_count} từ, rất ít thông tin")
        elif word_count <= 10:
            score = 30
            reasons.append(f"{word_count} từ, còn thiếu chi tiết")
        elif word_count <= 20:
            score = 50
            reasons.append(f"{word_count} từ, độ chi tiết trung bình")
        else:
            score = 60
            reasons.append(f"{word_count} từ, khá chi tiết")

        # Boost: specific action keywords
        if has_specific:
            score += 20
            reasons.append("Có action cụ thể (tạo file, sửa lỗi, ...)")

        if has_action and has_file:
            score += 15
            reasons.append("Có cả action + file path, rõ ràng")

        # Boost: file extension
        if has_file:
            score += 10
            reasons.append("Có đường dẫn/đuôi file cụ thể")

        # Boost: action keyword
        if has_action:
            score += 10
            reasons.append("Có action keyword")

        # Boost: context available
        if has_context and has_action:
            score += 5
            reasons.append("Có context dự án hỗ trợ")

        # Penalty: clarification keywords (nghi ngờ, hỏi)

        penalty = 0
        if has_clarification:
            penalty += 15
            reasons.append("Có từ khóa nghi vấn — có thể đang hỏi, không phải yêu cầu")

        # Penalty: very short with no action
        if word_count <= 5 and not has_action:
            penalty += 20
            reasons.append("Rất ngắn và không có action — có thể chỉ chào hỏi")

        score = max(0, min(100, score - penalty))

        needs_clarification = score < 60

        questions = []
        if needs_clarification:
            if not has_action and not has_file:
                questions.append("Bạn muốn tôi làm gì? (tạo file, sửa code, chạy lệnh, ...)")
            if has_action and not has_file:
                questions.append("Bạn muốn thao tác trên file nào?")
            if word_count <= 5:
                questions.append("Bạn có thể mô tả chi tiết hơn được không?")

        return ConfidenceScore(
            score=score,
            reason="; ".join(reasons),
            needs_clarification=needs_clarification,
            suggested_questions=questions,
        )