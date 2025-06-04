// تابع نمایش دلیل رد
function showRejectionReason(reason, comments) {
    document.getElementById('rejectionReason').textContent = reason || 'دلیل مشخص نشده است.';
    
    var commentsSection = document.getElementById('rejectionCommentsSection');
    var commentsElement = document.getElementById('rejectionComments');
    
    if (comments && comments.trim() !== '') {
        commentsElement.textContent = comments;
        commentsSection.style.display = 'block';
    } else {
        commentsSection.style.display = 'none';
    }
}

// تابع تایید حذف
function confirmDelete(attendanceId) {
    if (confirm('آیا از حذف این ساعت کاری مطمئن هستید؟')) {
        window.location.href = '/hr/attendance/delete/' + attendanceId + '/';
    }
} 